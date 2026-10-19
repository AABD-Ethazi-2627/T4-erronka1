"""FastAPI service for CNC predictive-maintenance scoring."""

from contextlib import asynccontextmanager
from datetime import datetime
import logging
import os
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


logger = logging.getLogger(__name__)

MODEL_PATH = os.getenv("MODEL_PATH", "/models/cnc_failure_model.pkl")
FEATURE_COLUMNS = [
    "air_temp_K",
    "process_temp_K",
    "rpm",
    "torque_Nm",
    "tool_wear_min",
]
FAILURE_TYPE_COLUMNS = [
    "failure_TWF",
    "failure_HDF",
    "failure_PWF",
    "failure_OSF",
    "failure_RNF",
]
FAILURE_TYPE_NAMES = {
    "failure_TWF": "TWF",
    "failure_HDF": "HDF",
    "failure_PWF": "PWF",
    "failure_OSF": "OSF",
    "failure_RNF": "RNF",
}


class SensorReading(BaseModel):
    """Sensor payload sent by NiFi to the scoring service."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    machine_id: str = Field(min_length=1, max_length=64)
    machine_type: Literal["H", "M", "L"]
    air_temp_K: float
    process_temp_K: float
    rpm: float
    torque_Nm: float
    tool_wear_min: float


class Prediction(BaseModel):
    machine_id: str
    failure_predicted: bool
    failure_probability: float = Field(ge=0, le=1)
    alert_level: Literal["OK", "KONTUZ", "LARRIA"]
    failure_types: list[str]
    failure_type_probabilities: dict[str, float]
    anomaly_detected: bool
    anomaly_score: float | None = None


def _load_model() -> object | None:
    """Load the model once during application startup."""

    if not os.path.isfile(MODEL_PATH):
        logger.warning("Model file not found: %s", MODEL_PATH)
        return None

    model = joblib.load(MODEL_PATH)
    logger.info("Loaded scoring model from %s", MODEL_PATH)
    return model


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = _load_model()
    app.state.model_path = MODEL_PATH
    yield
    app.state.model = None


app = FastAPI(
    title="CNC Failure Scoring API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"message": "CNC Scoring API Activa"}


@app.get("/health")
def health(request: Request):
    model = getattr(request.app.state, "model", None)
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "model_path": request.app.state.model_path,
    }


def _failure_probability(model: object, features: pd.DataFrame) -> float:
    """Return the probability for class 1, independent of class ordering."""

    if not hasattr(model, "predict_proba"):
        raise ValueError("The configured model does not expose predict_proba")

    probabilities = model.predict_proba(features)[0]
    classes = list(getattr(model, "classes_", range(len(probabilities))))
    try:
        failure_index = classes.index(1)
    except ValueError:
        failure_index = min(1, len(probabilities) - 1)
    return float(probabilities[failure_index])


def _failure_type_predictions(
    model: object | None,
    features: pd.DataFrame,
    columns: list[str],
) -> tuple[list[str], dict[str, float]]:
    """Return predicted failure modes and their class-1 probabilities."""

    if model is None:
        return [], {}

    predictions = model.predict(features)[0]
    probabilities = model.predict_proba(features)
    estimators = model.named_steps["classifier"].estimators_
    scores: dict[str, float] = {}
    predicted_types: list[str] = []

    for index, column in enumerate(columns):
        estimator = estimators[index]
        classes = list(getattr(estimator, "classes_", [0, 1]))
        failure_index = classes.index(1) if 1 in classes else min(1, len(classes) - 1)
        probability = float(probabilities[index][0][failure_index])
        name = FAILURE_TYPE_NAMES.get(column, column)
        scores[name] = round(probability, 4)
        if bool(predictions[index]):
            predicted_types.append(name)

    return predicted_types, scores


def _anomaly_prediction(
    model: object | None,
    features: pd.DataFrame,
) -> tuple[bool, float | None]:
    """Return whether the IsolationForest flags the reading as anomalous."""

    if model is None:
        return False, None

    prediction = int(model.predict(features)[0])
    score = float(model.decision_function(features)[0])
    return prediction == -1, round(score, 4)


def _alert_level(
    probability: float,
    anomaly_detected: bool,
) -> Literal["OK", "KONTUZ", "LARRIA"]:
    if probability < 0.5:
        if anomaly_detected:
            return "KONTUZ"
        return "OK"
    if probability < 0.8:
        return "KONTUZ"
    return "LARRIA"


@app.post("/predict", response_model=Prediction)
def predict(payload: SensorReading, request: Request):
    model = getattr(request.app.state, "model", None)
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Scoring model is not loaded",
        )

    if isinstance(model, dict):
        overall_model = model.get("overall_model")
        failure_type_model = model.get("failure_type_model")
        anomaly_model = model.get("anomaly_model")
        feature_columns = model.get("feature_columns", [*FEATURE_COLUMNS, "machine_type"])
        failure_type_columns = model.get("failure_type_columns", FAILURE_TYPE_COLUMNS)
    else:
        overall_model = model
        failure_type_model = None
        anomaly_model = None
        feature_columns = FEATURE_COLUMNS
        failure_type_columns = []

    values = {
        "air_temp_K": payload.air_temp_K,
        "process_temp_K": payload.process_temp_K,
        "rpm": payload.rpm,
        "torque_Nm": payload.torque_Nm,
        "tool_wear_min": payload.tool_wear_min,
        "machine_type": payload.machine_type,
    }
    features = pd.DataFrame([{column: values[column] for column in feature_columns}])

    try:
        failure_probability = _failure_probability(overall_model, features)
        failure_predicted = bool(overall_model.predict(features)[0])
        failure_types, failure_type_probabilities = _failure_type_predictions(
            failure_type_model,
            features,
            failure_type_columns,
        )
        anomaly_detected, anomaly_score = _anomaly_prediction(anomaly_model, features)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        logger.exception("Model prediction failed")
        raise HTTPException(status_code=500, detail="Model prediction failed") from exc

    return Prediction(
        machine_id=payload.machine_id,
        failure_predicted=failure_predicted,
        failure_probability=round(failure_probability, 4),
        alert_level=_alert_level(failure_probability, anomaly_detected),
        failure_types=failure_types,
        failure_type_probabilities=failure_type_probabilities,
        anomaly_detected=anomaly_detected,
        anomaly_score=anomaly_score,
    )
