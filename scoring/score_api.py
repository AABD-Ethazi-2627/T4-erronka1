"""CNC makinen mantentze prediktiborako FastAPI scoring-zerbitzua.

API honek NiFitik jasotako sentsore-irakurketa balidatzen du, entrenatutako
eredua erabiliz hutsegitearen probabilitatea eta alerta-maila kalkulatzen ditu,
eta emaitza JSON moduan itzultzen du.
"""

# FastAPIren lifespan mekanismoa: aplikazioa abiatzean eta ixtean kodea
# exekutatzeko erabiltzen da; hemen modeloa behin kargatzeko erabiltzen dugu.
from contextlib import asynccontextmanager
# ``datetime``: sarrerako timestamp-a data-objektu gisa balidatzeko.
from datetime import datetime
# ``logging``: zerbitzuko abisuak eta akatsak erregistratzeko.
import logging
# ``os``: ingurune-aldagaietatik model-path-a irakurtzeko eta fitxategia
# existitzen den egiaztatzeko.
import os
# ``Literal``: Pydantic-i onartutako testu-balioen zerrenda mugatzeko.
from typing import Literal

# ``joblib``: train_model.py-k sortutako .pkl artifact-a kargatzeko.
import joblib
# ``pandas``: APIko sarrerako balioak DataFrame bihurtzeko, scikit-learn-ek
# espero duen formatuan.
import pandas as pd
# FastAPI: HTTP aplikazioa sortzeko; HTTPException errore kontrolatuetarako eta
# Request aplikazioaren state-ra iristeko.
from fastapi import FastAPI, HTTPException, Request
# Pydantic: eskaera eta erantzun JSONen egitura eta motak balidatzeko.
from pydantic import BaseModel, ConfigDict, Field


# Logger honek APIaren abio-, karga- eta predikzio-akatsak jasotzen ditu.
logger = logging.getLogger(__name__)

# ``MODEL_PATH``: Docker-en /models/... izan ohi da; MODEL_PATH ingurune-
# aldagaiak balio hori ordezkatu dezake.
MODEL_PATH = os.getenv("MODEL_PATH", "/models/cnc_failure_model.pkl")
# Entrenamenduan erabili ziren jatorrizko sentsore-zutabe numerikoak.
FEATURE_COLUMNS = [
    "air_temp_K",
    "process_temp_K",
    "rpm",
    "torque_Nm",
    "tool_wear_min",
]
# APIan entrenamenduaren modu berean berriro kalkulatzen diren ezaugarriak.
ENGINEERED_FEATURE_COLUMNS = ["temp_diff", "power_est"]
# Eredu multi-output-ak aurreikusten dituen hutsegite moten zutabe-izenak.
FAILURE_TYPE_COLUMNS = [
    "failure_TWF",
    "failure_HDF",
    "failure_PWF",
    "failure_OSF",
    "failure_RNF",
]
# Barneko zutabe-izen teknikoa erabiltzailearentzat ulergarriagoa den izenera
# bihurtzeko mapa, adibidez failure_TWF -> TWF.
FAILURE_TYPE_NAMES = {
    "failure_TWF": "TWF",
    "failure_HDF": "HDF",
    "failure_PWF": "PWF",
    "failure_OSF": "OSF",
    "failure_RNF": "RNF",
}

# Atalase kritikoa alertaren lehentasuna adierazteko. Atalase ekonomikoa,
# berriz, entrenatutako artifact-ean dago eta datu berriekin alda daiteke.
CRITICAL_FAILURE_THRESHOLD = 0.8


class SensorReading(BaseModel):
    """NiFik scoring APIra bidaltzen duen sentsore-datuen egitura.

    Pydantic-ek JSONaren eremuak, motak eta mugak automatikoki egiaztatzen ditu.
    ``extra='forbid'`` konfigurazioak definitu gabeko eremuak baztertzen ditu,
    APIari espero ez duen daturik ez bidaltzeko.
    """

    # Eremu gehigarriak ez onartu; eskaerak kontratu zehatza bete behar du.
    model_config = ConfigDict(extra="forbid")

    # CSV/JSON sarrerako timestamp-a data eta ordu baliozko bihurtu.
    timestamp: datetime
    # Makinaren identifikatzailea; gutxienez karaktere 1 eta gehienez 64.
    machine_id: str = Field(min_length=1, max_length=64)
    # Kalitatea bakarrik H, M edo L izan daiteke.
    machine_type: Literal["H", "M", "L"]
    # Ereduak behar dituen bost sentsore-neurriak.
    air_temp_K: float
    process_temp_K: float
    rpm: float
    torque_Nm: float
    tool_wear_min: float


class Prediction(BaseModel):
    """APIak itzultzen duen predikzioaren JSON kontratua.

    Klase honi esker FastAPIk erantzunaren egitura egiaztatu eta Swagger
    dokumentazioan automatikoki erakusten du.
    """

    # Jatorrizko irakurketatik datozen identifikazio-eremuak.
    timestamp: datetime
    machine_id: str
    machine_type: Literal["H", "M", "L"]
    # Hutsegite orokorraren aurreikuspen bitarra.
    failure_predicted: bool
    # 0 eta 1 arteko hutsegite-probabilitatea.
    failure_probability: float = Field(ge=0, le=1)
    # Probabilitatearen eta anomaliaren arabera kalkulatutako alerta-maila.
    alert_level: Literal["OK", "KONTUZ", "LARRIA"]
    # Aurreikusitako hutsegite-moten zerrenda.
    failure_types: list[str]
    # Hutsegite mota bakoitzaren 0-1 probabilitateak.
    failure_type_probabilities: dict[str, float]
    # IsolationForest-ek irakurketa anomaliatzat jo duen ala ez.
    anomaly_detected: bool
    # IsolationForest-en decision_function puntuazioa; batzuetan None izan daiteke.
    anomaly_score: float | None = None


def _load_model() -> object | None:
    """Entrenatutako model artifact-a behin kargatu aplikazioa abiatzean.

    ``MODEL_PATH``-en fitxategia ez badago, ``None`` itzultzen da eta APIak
    ``/health``-en modeloa ez dagoela erakutsiko du; ``/predict``-ek 503 itzuliko
    du. Fitxategia badago, ``joblib.load``-ek train_model.py-ko dictionary-a
    (ereduak, ezaugarriak eta atalasea) kargatzen du.
    """

    # Modeloa aurkitu ezin bada, abisua logeatu eta zerbitzua modelorik gabe utzi.
    if not os.path.isfile(MODEL_PATH):
        logger.warning("Model file not found: %s", MODEL_PATH)
        return None

    # .pkl fitxategiko artifact-a memorian kargatu.
    model = joblib.load(MODEL_PATH)
    logger.info("Loaded scoring model from %s", MODEL_PATH)
    return model


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPIren bizi-zikloa kudeatu.

    Aplikazioa hasi aurretik modeloa kargatzen da eta aplikazioa ixtean
    erreferentzia ezabatzen da. Horrela, eskaera bakoitzean diskoa irakurri
    beharrean, modeloa behin bakarrik kargatzen da.
    """

    # ``app.state`` objektuan partekatutako modeloa eta bere bidea gorde.
    app.state.model = _load_model()
    app.state.model_path = MODEL_PATH
    # ``yield`` bitartean FastAPI aplikazioa eskaerak jasotzen ari da.
    yield
    # Aplikazioa ixtean modeloa askatu.
    app.state.model = None


# FastAPI aplikazio nagusia: Swagger /docs eta OpenAPI eskema sortzen ditu.
app = FastAPI(
    title="CNC Failure Scoring API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    """APIa martxan dagoela adierazten duen oinarrizko endpoint-a."""

    return {"message": "CNC Scoring API Activa"}


@app.get("/health")
def health(request: Request):
    """Zerbitzuaren eta modeloa kargatuta dagoen egoera itzuli.

    ``request.app.state.model``-ek abioan kargatutako modeloa jasotzen du.
    Endpoint hau Docker/NiFi monitorizaziorako erabil daiteke, predikzio bat
    egin gabe.
    """

    # Aplikazioaren state-tik modeloa irakurri; baliteke None izatea.
    model = getattr(request.app.state, "model", None)
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "model_path": request.app.state.model_path,
    }


def _failure_probability(model: object, features: pd.DataFrame) -> float:
    """Hutsegitearen, hau da, 1 klasearen probabilitatea kalkulatu.

    Scikit-learn-ek ``predict_proba``-ren zutabe-ordena modeloko classes_
    atributuaren arabera ematen du. Horregatik ez dugu itsu-itsuan bigarren
    zutabea hartu nahi: lehenik 1 klasearen benetako indizea bilatzen dugu.
    ``features`` APIko payloadetik sortutako DataFramea da.
    """

    # Ereduak probabilitateak kalkulatzeko metodoa duen egiaztatu.
    if not hasattr(model, "predict_proba"):
        raise ValueError("The configured model does not expose predict_proba")

    # Lehenengo (eta kasu bakarreko) errenkadaren probabilitateak atera.
    probabilities = model.predict_proba(features)[0]
    # Klaseen etiketa errealak lortu, adibidez [0, 1].
    classes = list(getattr(model, "classes_", range(len(probabilities))))
    try:
        # 1 klasea aurkitu: hori da hutsegite positiboa.
        failure_index = classes.index(1)
    except ValueError:
        # Ereduak 1 klasea ez badu, azken aukera gisa bigarren posizioa erabili.
        failure_index = min(1, len(probabilities) - 1)
    return float(probabilities[failure_index])


def _failure_type_predictions(
    model: object | None,
    features: pd.DataFrame,
    columns: list[str],
) -> tuple[list[str], dict[str, float]]:
    """Hutsegite-motak eta mota bakoitzaren 1 klaseko probabilitatea itzuli.

    ``model`` MultiOutputClassifier duen Pipeline-a da. Irteera bakoitza
    (TWF, HDF, PWF, OSF eta RNF) banaka aztertzen da. ``model`` None bada,
    artifact zahar edo sinple batekin ari garela esan nahi du eta emaitza hutsak
    itzultzen dira.
    """

    # Ez badago mota anitzen modelorik, ez dago mota-iragarpenik egiteko.
    if model is None:
        return [], {}

    # Mota bakoitzeko 0/1 aurreikuspenak lortu.
    predictions = model.predict(features)[0]
    # Mota bakoitzaren probabilitate-zerrenda lortu.
    probabilities = model.predict_proba(features)
    # Pipeline barruko MultiOutputClassifier-eko estimator bakoitza eskuratu.
    estimators = model.named_steps["classifier"].estimators_
    # Erantzunean itzuliko diren emaitzen egiturak.
    scores: dict[str, float] = {}
    predicted_types: list[str] = []

    for index, column in enumerate(columns):
        # Uneko hutsegite-motari dagokion Random Foresta aukeratu.
        estimator = estimators[index]
        # Estimator horren klase-ordena kontuan hartu.
        classes = list(getattr(estimator, "classes_", [0, 1]))
        # 1 klasearen probabilitatearen indizea bilatu.
        failure_index = classes.index(1) if 1 in classes else min(1, len(classes) - 1)
        # Uneko motaren probabilitatea biribilduta gorde.
        probability = float(probabilities[index][0][failure_index])
        name = FAILURE_TYPE_NAMES.get(column, column)
        scores[name] = round(probability, 4)
        # Aurreikuspen bitarra 1 bada, mota zerrendara gehitu.
        if bool(predictions[index]):
            predicted_types.append(name)

    return predicted_types, scores


def _anomaly_prediction(
    model: object | None,
    features: pd.DataFrame,
) -> tuple[bool, float | None]:
    """IsolationForest-ek irakurketa anomaliatzat hartu duen kalkulatu.

    IsolationForest-en irteeran ``-1`` anomalia da eta ``1`` ohiko irakurketa.
    ``decision_function``-ek anomalia-scorea ematen du; score txikiagoak
    anomalia-portaera handiagoa adierazten du.
    """

    # Modelorik ez badago, ezin da anomalia kalkulatu.
    if model is None:
        return False, None

    # IsolationForest-en etiketa hartu: -1 edo 1.
    prediction = int(model.predict(features)[0])
    # Uneko datuaren anomalia-scorea kalkulatu.
    score = float(model.decision_function(features)[0])
    return prediction == -1, round(score, 4)


def _alert_level(
    probability: float,
    anomaly_detected: bool,
    failure_predicted: bool,
    failure_threshold: float,
) -> Literal["OK", "KONTUZ", "LARRIA"]:
    """Probabilitatea eta anomalia erabiliz alerta-maila esleitu.

    ``OK``: atalase ekonomikoa baino probabilitate txikiagoa eta anomaliarik ez.
    ``KONTUZ``: atalase ekonomikoa gainditu da edo anomalia dago.
    ``LARRIA``: probabilitatea %80 edo handiagoa.

    ``failure_threshold`` entrenamendu-balidazioan kostu ekonomikoaren arabera
    aukeratutako atalasea da; horrela APIko ``failure_predicted`` eta koloreko
    alerta-maila ez dira elkarren kontra joaten.
    """

    # Probabilitate oso altuak LARRIA dira, independenteki atalase ekonomikoaz.
    if probability >= CRITICAL_FAILURE_THRESHOLD:
        return "LARRIA"
    # Atalase ekonomikoa edo anomalia gainditzen bada, gutxienez KONTUZ.
    if probability >= failure_threshold or anomaly_detected or failure_predicted:
        return "KONTUZ"
    return "OK"


@app.post("/predict", response_model=Prediction)
def predict(payload: SensorReading, request: Request):
    """Sentsore-irakurketa jaso eta mantentze-predikzioa itzuli.

    ``payload`` NiFik bidalitako eta Pydantic-ek balidatutako sarrera da.
    Funtzioak artifact-eko hiru modeloei deitzen die, probabilitateak eta
    alertak kalkulatzen ditu, eta ``Prediction`` erantzun egituratua itzultzen
    du. Modeloa falta bada 503 itzultzen da; iragarpenak huts egiten badu 500.
    """

    # Abioan state-n kargatutako modeloa eskuratu.
    model = getattr(request.app.state, "model", None)
    if model is None:
        # Zerbitzua bizirik egon arren modeloa gabe ezin da iragarpenik egin.
        raise HTTPException(
            status_code=503,
            detail="Scoring model is not loaded",
        )

    # Gure artifact-a dictionary-a da; atzerako bateragarritasunerako, Pipeline
    # bakarra zuzenean kargatutako kasua ere onartzen dugu.
    if isinstance(model, dict):
        # Artifact-etik behar diren ereduak eta konfigurazioa atera.
        overall_model = model.get("overall_model")
        failure_type_model = model.get("failure_type_model")
        anomaly_model = model.get("anomaly_model")
        feature_columns = model.get(
            "feature_columns",
            [*FEATURE_COLUMNS, *ENGINEERED_FEATURE_COLUMNS, "machine_type"],
        )
        failure_type_columns = model.get("failure_type_columns", FAILURE_TYPE_COLUMNS)
        failure_threshold = float(model.get("failure_threshold", 0.5))
    else:
        # Artifact zaharrago batek Pipeline bakarra izan dezake.
        overall_model = model
        failure_type_model = None
        anomaly_model = None
        feature_columns = FEATURE_COLUMNS
        failure_type_columns = []
        failure_threshold = 0.5

    # Payloadeko sentsoreak eta APIan kalkulatutako feature engineering-a
    # dictionary batean bildu.
    values = {
        "air_temp_K": payload.air_temp_K,
        "process_temp_K": payload.process_temp_K,
        "rpm": payload.rpm,
        "torque_Nm": payload.torque_Nm,
        "tool_wear_min": payload.tool_wear_min,
        "temp_diff": payload.process_temp_K - payload.air_temp_K,
        "power_est": payload.rpm * payload.torque_Nm,
        "machine_type": payload.machine_type,
    }
    # Ereduak espero duen zutabe-ordena errespetatuz DataFramea sortu.
    features = pd.DataFrame([{column: values[column] for column in feature_columns}])

    try:
        # Hutsegite orokorraren probabilitatea kalkulatu.
        failure_probability = _failure_probability(overall_model, features)
        # Entrenamenduan aukeratutako atalasearen arabera 0/1 erabakia hartu.
        failure_predicted = failure_probability >= failure_threshold
        # Hutsegite mota posibleak eta probabilitateak kalkulatu.
        failure_types, failure_type_probabilities = _failure_type_predictions(
            failure_type_model,
            features,
            failure_type_columns,
        )
        # IsolationForest-en anomalia-egoera eta scorea kalkulatu.
        anomaly_detected, anomaly_score = _anomaly_prediction(anomaly_model, features)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        # Stack trace-a loggera bidali, baina bezeroari mezu kontrolatua itzuli.
        logger.exception("Model prediction failed")
        raise HTTPException(status_code=500, detail="Model prediction failed") from exc

    # Emaitza APIaren kontratuaren arabera sortu eta FastAPIk JSON bihurtuko du.
    return Prediction(
        timestamp=payload.timestamp,
        machine_id=payload.machine_id,
        machine_type=payload.machine_type,
        failure_predicted=failure_predicted,
        failure_probability=round(failure_probability, 4),
        alert_level=_alert_level(
            failure_probability,
            anomaly_detected,
            failure_predicted,
            failure_threshold,
        ),
        failure_types=failure_types,
        failure_type_probabilities=failure_type_probabilities,
        anomaly_detected=anomaly_detected,
        anomaly_score=anomaly_score,
    )
