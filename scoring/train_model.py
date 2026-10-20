"""Clean the training CSV, evaluate the models, and save them for the API."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report
from sklearn.metrics import confusion_matrix
from sklearn.metrics import f1_score
from sklearn.metrics import precision_recall_curve
from sklearn.metrics import precision_score
from sklearn.metrics import recall_score
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "ai4i2020_train.csv"
MODEL_PATH = ROOT / "models" / "cnc_failure_model.pkl"

FEATURE_COLUMNS = [
    "air_temp_K",
    "process_temp_K",
    "rpm",
    "torque_Nm",
    "tool_wear_min",
]
ENGINEERED_FEATURE_COLUMNS = ["temp_diff", "power_est"]
QUALITY_COLUMN = "machine_type"
TARGET_COLUMN = "machine_failure"
FAILURE_TYPE_COLUMNS = [
    "failure_TWF",
    "failure_HDF",
    "failure_PWF",
    "failure_OSF",
    "failure_RNF",
]
NUMERIC_COLUMNS = [*FEATURE_COLUMNS, TARGET_COLUMN, *FAILURE_TYPE_COLUMNS]


def _make_preprocessor(numeric_columns: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", numeric_columns),
            ("quality", OneHotEncoder(handle_unknown="ignore"), [QUALITY_COLUMN]),
        ]
    )


def clean_training_data(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize columns and remove unusable training rows."""

    data = data.copy()
    rows_loaded = len(data)
    data.columns = data.columns.str.strip()

    for column in ("machine_id", QUALITY_COLUMN):
        if column in data.columns:
            data[column] = data[column].astype("string").str.strip()

    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    before = len(data)
    data = data.drop_duplicates()
    duplicates_removed = before - len(data)

    before = len(data)
    data = data.dropna(
        subset=[*FEATURE_COLUMNS, QUALITY_COLUMN, TARGET_COLUMN, *FAILURE_TYPE_COLUMNS]
    )
    missing_removed = before - len(data)

    data = data[data[QUALITY_COLUMN].isin(["H", "M", "L"])]
    data = data[data[[TARGET_COLUMN, *FAILURE_TYPE_COLUMNS]].isin([0, 1]).all(axis=1)]
    if data.empty:
        raise ValueError("No valid training rows remain after cleaning")

    print(f"Rows loaded: {rows_loaded}")
    print(f"Duplicates removed: {duplicates_removed}")
    print(f"Rows with missing required values removed: {missing_removed}")
    print(f"Rows used for training: {len(data)}")
    print(f"Machine quality distribution: {data[QUALITY_COLUMN].value_counts().to_dict()}")
    print(f"Target distribution: {data[TARGET_COLUMN].value_counts().to_dict()}")
    print("Failure type distribution:")
    print(data[FAILURE_TYPE_COLUMNS].sum().to_dict())
    return data


def add_engineered_features(data: pd.DataFrame) -> pd.DataFrame:
    """Add physically interpretable features used by training and inference."""

    data = data.copy()
    data["temp_diff"] = data["process_temp_K"] - data["air_temp_K"]
    data["power_est"] = data["rpm"] * data["torque_Nm"]
    return data


def choose_failure_threshold(
    y_true: pd.Series,
    probabilities: np.ndarray,
    target_recall: float = 0.76,
) -> tuple[float, dict[str, float]]:
    """Choose a threshold that prioritizes recall while retaining useful precision."""

    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)
    candidates = []
    for index, threshold in enumerate(thresholds):
        if recall[index] >= target_recall:
            candidates.append(
                (
                    f1_score(y_true, probabilities >= threshold, zero_division=0),
                    precision[index],
                    recall[index],
                    float(threshold),
                )
            )

    if candidates:
        _, candidate_precision, candidate_recall, selected = max(candidates)
    else:
        index = int(np.argmax(recall[:-1]))
        selected = float(thresholds[index])
        candidate_precision = float(precision[index])
        candidate_recall = float(recall[index])

    return selected, {
        "target_recall": target_recall,
        "validation_recall": round(candidate_recall, 4),
        "validation_precision": round(candidate_precision, 4),
    }


def evaluate_failure_model(
    model: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> tuple[float, dict[str, object]]:
    """Print validation metrics and return the tuned threshold plus metrics."""

    probabilities = model.predict_proba(X_test)[:, 1]
    default_predictions = probabilities >= 0.5
    threshold, threshold_metrics = choose_failure_threshold(y_test, probabilities)
    tuned_predictions = probabilities >= threshold

    print("\nOverall failure validation (default threshold=0.50):")
    print(classification_report(y_test, default_predictions, zero_division=0))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, default_predictions).tolist())
    print(f"ROC-AUC: {roc_auc_score(y_test, probabilities):.4f}")

    print(f"\nTuned threshold: {threshold:.4f}")
    print(classification_report(y_test, tuned_predictions, zero_division=0))
    print("Tuned confusion matrix:")
    print(confusion_matrix(y_test, tuned_predictions).tolist())
    print(
        "Tuned metrics: "
        f"recall={recall_score(y_test, tuned_predictions, zero_division=0):.4f}, "
        f"precision={precision_score(y_test, tuned_predictions, zero_division=0):.4f}, "
        f"f1={f1_score(y_test, tuned_predictions, zero_division=0):.4f}"
    )

    metrics = {
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
        "default_confusion_matrix": confusion_matrix(y_test, default_predictions).tolist(),
        "tuned_confusion_matrix": confusion_matrix(y_test, tuned_predictions).tolist(),
        "tuned_threshold": round(threshold, 4),
        **threshold_metrics,
    }
    return threshold, metrics


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Training data not found: {DATA_PATH}")

    cleaned = add_engineered_features(clean_training_data(pd.read_csv(DATA_PATH)))
    numeric_feature_columns = [*FEATURE_COLUMNS, *ENGINEERED_FEATURE_COLUMNS]
    feature_columns = [*numeric_feature_columns, QUALITY_COLUMN]
    X = cleaned[feature_columns]
    y = cleaned[TARGET_COLUMN].astype(int)
    y_failure_types = cleaned[FAILURE_TYPE_COLUMNS].astype(int)

    X_train, X_test, y_train, y_test, types_train, types_test = train_test_split(
        X,
        y,
        y_failure_types,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    overall_model = Pipeline(
        [
            ("preprocessor", _make_preprocessor(numeric_feature_columns)),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=100,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    overall_model.fit(X_train, y_train)

    failure_type_model = Pipeline(
        [
            ("preprocessor", _make_preprocessor(numeric_feature_columns)),
            (
                "classifier",
                MultiOutputClassifier(
                    RandomForestClassifier(
                        n_estimators=100,
                        class_weight="balanced",
                        random_state=42,
                    )
                ),
            ),
        ]
    )
    failure_type_model.fit(X_train, types_train)

    anomaly_model = Pipeline(
        [
            ("preprocessor", _make_preprocessor(numeric_feature_columns)),
            (
                "detector",
                IsolationForest(
                    n_estimators=200,
                    contamination=0.02,
                    random_state=42,
                ),
            ),
        ]
    )
    normal_rows = X_train[y_train == 0]
    anomaly_model.fit(normal_rows)

    failure_threshold, evaluation_metrics = evaluate_failure_model(
        overall_model,
        X_test,
        y_test,
    )

    classifier = overall_model.named_steps["classifier"]
    print("Feature importance:")
    transformed_names = [
        *numeric_feature_columns,
        *overall_model.named_steps["preprocessor"]
        .named_transformers_["quality"]
        .get_feature_names_out([QUALITY_COLUMN]),
    ]
    print(
        dict(
            sorted(
                zip(transformed_names, classifier.feature_importances_),
                key=lambda item: item[1],
                reverse=True,
            )
        )
    )

    print("Failure type validation:")
    type_predictions = failure_type_model.predict(X_test)
    for index, column in enumerate(FAILURE_TYPE_COLUMNS):
        print(f"\n{column}:")
        print(
            classification_report(
                types_test.iloc[:, index],
                type_predictions[:, index],
                zero_division=0,
            )
        )

    anomaly_flags = anomaly_model.predict(X_test) == -1
    print("\nIsolationForest anomaly validation:")
    print(classification_report(y_test, anomaly_flags, zero_division=0))

    model_artifact = {
        "version": 3,
        "overall_model": overall_model,
        "failure_type_model": failure_type_model,
        "anomaly_model": anomaly_model,
        "feature_columns": feature_columns,
        "engineered_feature_columns": ENGINEERED_FEATURE_COLUMNS,
        "failure_type_columns": FAILURE_TYPE_COLUMNS,
        "failure_threshold": failure_threshold,
        "evaluation": evaluation_metrics,
        "quality_values": {"H": "High", "M": "Medium", "L": "Low"},
    }

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_artifact, MODEL_PATH)
    print(f"Model saved to: {MODEL_PATH}")


if __name__ == "__main__":
    main()
