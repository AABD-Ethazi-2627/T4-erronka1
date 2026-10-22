"""Prestakuntza-datuak garbitu, ereduak entrenatu eta APIarentzat gorde.

Fitxategi honek ez du APIaren eskaerarik prozesatzen. Entrenamendu offline-a
egiten du: CSVa irakurri, datuak garbitu, ezaugarri berriak sortu, ereduak
ebaluatu eta azken eredu-paketea ``models/cnc_failure_model.pkl`` fitxategian
gordetzen du.
"""

# ``Path``: fitxategi- eta karpeta-bideak sistema eragilearen arabera
# modu seguruan eraikitzeko erabiltzen da.
from pathlib import Path

# ``joblib``: scikit-learn ereduak eta Python objektuak diskoan gordetzeko.
import joblib
# ``numpy``: array numerikoekin eta probabilitateekin eragiketak egiteko.
import numpy as np
# ``pandas``: CSVko taulak irakurri eta DataFrame moduan manipulatzeko.
import pandas as pd
# ``ColumnTransformer``: zutabe numerikoei eta kategorikoei aurreprozesaketa
# desberdina aplikatzeko.
from sklearn.compose import ColumnTransformer
# Random Forest: sentsore-datuetatik hutsegitea sailkatzeko eredu gainbegiratua.
from sklearn.ensemble import RandomForestClassifier
# Isolation Forest: etiketarik gabeko portaera anomaloei antzemateko eredua.
from sklearn.ensemble import IsolationForest
# Sailkapenaren txostena: precision, recall eta F1 bezalako metrikak inprimatzeko.
from sklearn.metrics import classification_report
# Confusion matrix: benetako eta aurreikusitako klaseak alderatzeko.
from sklearn.metrics import confusion_matrix
# F1: precision eta recall-en arteko oreka neurtzeko.
from sklearn.metrics import f1_score
# Precision: positibo gisa aurreikusitakoen artean zenbat diren zuzenak neurtzeko.
from sklearn.metrics import precision_score
# Recall: benetako hutsegiteen artean zenbat detektatzen diren neurtzeko.
from sklearn.metrics import recall_score
# ROC-AUC: eredua klaseak bereizteko gai den neurtzeko.
from sklearn.metrics import roc_auc_score
# Datuak entrenamendu- eta balidazio-multzoetan banatzeko.
from sklearn.model_selection import train_test_split
# Irteera anitzeko sailkapena: hutsegite mota bakoitzerako iragarpena egiteko.
from sklearn.multioutput import MultiOutputClassifier
# Aurreprozesaketa eta sailkatzailea urrats bakarrean lotzeko.
from sklearn.pipeline import Pipeline
# H, M eta L bezalako testu-kategoriak zutabe bitar bihurtzeko.
from sklearn.preprocessing import OneHotEncoder


# Proiektuaren erroa: ``scoring`` karpetaren gurasoa.
ROOT = Path(__file__).resolve().parent.parent
# Entrenamendurako erabiltzen den AI4I CSVaren kokapena.
DATA_PATH = ROOT / "data" / "ai4i2020_train.csv"
# APIak abioan kargatuko duen eredu-paketearen kokapena.
MODEL_PATH = ROOT / "models" / "cnc_failure_model.pkl"

# Ereduari emango zaizkion jatorrizko sentsore-aldagai numerikoak.
FEATURE_COLUMNS = [
    "air_temp_K",
    "process_temp_K",
    "rpm",
    "torque_Nm",
    "tool_wear_min",
]
# Datuetatik kalkulatuko diren aldagai fisikoki interpretagarriak.
ENGINEERED_FEATURE_COLUMNS = ["temp_diff", "power_est"]
# Makinaren kalitate-maila: H=High, M=Medium eta L=Low.
QUALITY_COLUMN = "machine_type"
# Helburu nagusia: makina hondatuko den ala ez (0/1).
TARGET_COLUMN = "machine_failure"
# Bigarren mailako helburuak: hutsegite-mota bakoitzaren etiketak (0/1).
FAILURE_TYPE_COLUMNS = [
    "failure_TWF",
    "failure_HDF",
    "failure_PWF",
    "failure_OSF",
    "failure_RNF",
]

# Negozio-arazoaren kostuak: alerta batek teknikariaren 210 euroko bisita
# eragiten du, eta detektatu gabeko matxura batek 1.200 euroko geldialdia.
COST_REVIEW_EUR = 210.0
COST_MISSED_FAILURE_EUR = 1200.0
# Mantentze prediktiboan matxura gehienak detektatzea nahi dugu; kostu txikiena
# bilatuko da gutxienez recall-helburu hori betetzen duten atalaseen artean.
MIN_TARGET_RECALL = 0.76
# Zenbaki bihurtu behar diren zutabe guztiak. Kategoriaren zutabea ez da hemen
# sartzen, OneHotEncoder-ek testu gisa tratatu behar duelako.
NUMERIC_COLUMNS = [*FEATURE_COLUMNS, TARGET_COLUMN, *FAILURE_TYPE_COLUMNS]


def _make_preprocessor(numeric_columns: list[str]) -> ColumnTransformer:
    """Ereduen aurretik erabiliko den aurreprozesaketa definitu.

    ``numeric_columns`` parametroak ezaugarri numerikoen izenak jasotzen ditu.
    Zutabe horiek bere horretan pasatzen dira; ``machine_type`` kategorikoa,
    berriz, One-Hot Encoding bidez 0/1 zutabe bihurtzen da. ``Pipeline``-ek
    entrenamenduan eta APIko iragarpenetan prozesu bera aplikatzea bermatzen du.
    """
    return ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", numeric_columns),
            ("quality", OneHotEncoder(handle_unknown="ignore"), [QUALITY_COLUMN]),
        ]
    )


def clean_training_data(data: pd.DataFrame) -> pd.DataFrame:
    """Entrenamendu-DataFramea normalizatu eta baliogabeko errenkadak ezabatu.

    ``data`` CSVtik irakurritako taula da. Funtzioak zutabe-izenetako hutsuneak
    kentzen ditu, testu-kategoriak garbitzen ditu, zenbakiak bihurtzen ditu,
    bikoiztuak eta balio faltadun errenkadak ezabatzen ditu eta balio onargarriak
    soilik uzten ditu. Itzulera garbitutako DataFramea da.
    """

    # Jatorrizkoa ez aldatzeko kopia lokala sortzen dugu.
    data = data.copy()
    # CSVtik irakurritako errenkada kopurua, garbiketaren laburpenerako.
    rows_loaded = len(data)
    # Zutabe-izenetan ager daitezkeen hasierako/amaierako hutsuneak kentzen ditugu.
    data.columns = data.columns.str.strip()

    # IDa eta kalitate-kategoria testu gisa normalizatzen ditugu.
    for column in ("machine_id", QUALITY_COLUMN):
        if column in data.columns:
            data[column] = data[column].astype("string").str.strip()

    # Zutabe numerikoak zenbaki bihurtzen ditugu. Bihurtu ezin den balioa
    # ``NaN`` bihurtzen da eta ondoren dagokion errenkada ezabatuko da.
    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    # Errenkada guztiz berdinak ezabatu eta zenbat kendu diren kalkulatu.
    before = len(data)
    data = data.drop_duplicates()
    duplicates_removed = before - len(data)

    # Ereduak behar dituen zutabeetan balio falta duten errenkadak ezabatu.
    before = len(data)
    data = data.dropna(
        subset=[*FEATURE_COLUMNS, QUALITY_COLUMN, TARGET_COLUMN, *FAILURE_TYPE_COLUMNS]
    )
    missing_removed = before - len(data)

    # Makinaren kalitateak soilik H, M edo L izan daitezke.
    data = data[data[QUALITY_COLUMN].isin(["H", "M", "L"])]
    # Helburu nagusi eta sekundario guztiak 0 edo 1 izan behar dira.
    data = data[data[[TARGET_COLUMN, *FAILURE_TYPE_COLUMNS]].isin([0, 1]).all(axis=1)]
    if data.empty:
        raise ValueError("No valid training rows remain after cleaning")

    # Garbiketaren emaitza terminalean erakusten dugu, prozesua auditatu ahal izateko.
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
    """Ereduak entrenatzeko eta iragartzeko ezaugarri berriak kalkulatu.

    ``temp_diff`` prozesuaren eta airearen tenperaturen arteko diferentzia da.
    ``power_est`` gutxi gorabeherako potentzia da, RPM eta torquea biderkatuta.
    Bi kalkulu hauek APIan ere egiten dira, entrenamenduaren eta ekoizpenaren
    ezaugarriak berdinak izan daitezen.
    """

    # Jatorrizko DataFramea ez aldatzeko kopia erabiltzen dugu.
    data = data.copy()
    # Prozesuko tenperaturaren eta aireko tenperaturaren arteko diferentzia.
    data["temp_diff"] = data["process_temp_K"] - data["air_temp_K"]
    # Potentziaren estimazioa: biraketa-abiadura × torquea.
    data["power_est"] = data["rpm"] * data["torque_Nm"]
    return data


def choose_failure_threshold(
    y_true: pd.Series,
    probabilities: np.ndarray,
    target_recall: float = MIN_TARGET_RECALL,
    review_cost: float = COST_REVIEW_EUR,
    missed_failure_cost: float = COST_MISSED_FAILURE_EUR,
) -> tuple[float, dict[str, float]]:
    """Probabilitate-atalasea aukeratu, negozio-kostua minimizatuz.

    Ereduak 0 eta 1 arteko probabilitatea ematen du; atalaseak erabakitzen du
    noiz bihurtzen den probabilitate hori ``failure_predicted=True``. Mantentze
    prediktiboan faltsu negatiboak garestiak direnez, gutxienez
    ``target_recall`` recall lortu nahi dugu. Hautagaien artean alerta eta
    detektatu gabeko matxuren kostu oso txikiena duen atalasea aukeratzen da.
    Horrela, F1 ez da negozio-erabakiaren ordezko bakarra.
    """

    # Atalase posible guztiak probatu. 0 eta 1 gehitzeak muturreko erabakiak
    # ere kontuan hartzen ditu, eta threshold-ean probabilitate berdinak dauden
    # kasuetan portaera determinista mantentzen du.
    candidate_thresholds = np.unique(
        np.concatenate(([0.0, 1.0], np.asarray(probabilities, dtype=float)))
    )
    candidates: list[dict[str, float]] = []
    all_candidates: list[dict[str, float]] = []

    for threshold in candidate_thresholds:
        predictions = probabilities >= threshold
        tn, fp, fn, tp = confusion_matrix(
            y_true, predictions, labels=[0, 1]
        ).ravel()
        candidate_recall = recall_score(y_true, predictions, zero_division=0)
        candidate_precision = precision_score(y_true, predictions, zero_division=0)
        total_cost = (fp + tp) * review_cost + fn * missed_failure_cost
        candidate = {
            "threshold": float(threshold),
            "recall": float(candidate_recall),
            "precision": float(candidate_precision),
            "total_cost_eur": float(total_cost),
            "false_positives": float(fp),
            "false_negatives": float(fn),
            "true_positives": float(tp),
            "true_negatives": float(tn),
        }
        all_candidates.append(candidate)
        if candidate_recall >= target_recall:
            candidates.append(candidate)

    # Lehen aukera recall-helburua betetzen duten hautagaien artean egiten da.
    # Helburua ezinezkoa balitz, kostu txikiena duen atalase globala erabiltzen
    # dugu eta terminalean ohartarazten dugu.
    if candidates:
        selected_metrics = min(
            candidates,
            key=lambda item: (
                item["total_cost_eur"],
                -item["recall"],
                -item["precision"],
            ),
        )
    else:
        selected_metrics = min(
            all_candidates,
            key=lambda item: (
                item["total_cost_eur"],
                -item["recall"],
                -item["precision"],
            ),
        )
        print(
            "Warning: no threshold reached the target recall; "
            "selected the lowest-cost threshold."
        )

    selected = float(selected_metrics["threshold"])
    return selected, {
        "target_recall": target_recall,
        "validation_recall": round(selected_metrics["recall"], 4),
        "validation_precision": round(selected_metrics["precision"], 4),
        "validation_cost_eur": round(selected_metrics["total_cost_eur"], 2),
        "validation_false_positives": selected_metrics["false_positives"],
        "validation_false_negatives": selected_metrics["false_negatives"],
        "validation_true_positives": selected_metrics["true_positives"],
        "validation_true_negatives": selected_metrics["true_negatives"],
        "review_cost_eur": review_cost,
        "missed_failure_cost_eur": missed_failure_cost,
    }


def evaluate_failure_model(
    model: Pipeline,
    X_validation: pd.DataFrame,
    y_validation: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> tuple[float, dict[str, object]]:
    """Atalasea balidazioan aukeratu eta test independentean neurtu.

    ``X_validation``-ek atalasea aukeratzeko balio du; ``X_test`` ez da erabaki
    hori hartzeko erabiltzen, azken ebaluazio objektiboa egiteko baizik.
    Horrela ez dugu test-datuetan overfitting egiten.
    """

    # Balidazio-multzoan klase positiboaren probabilitatea atera.
    validation_probabilities = model.predict_proba(X_validation)[:, 1]
    threshold, threshold_metrics = choose_failure_threshold(
        y_validation, validation_probabilities
    )
    # Test-multzo independentean probabilitatea kalkulatu.
    probabilities = model.predict_proba(X_test)[:, 1]

    def summarize(
        labels: pd.Series,
        scores: np.ndarray,
        label: str,
    ) -> dict[str, object]:
        default_predictions = scores >= 0.5
        tuned_predictions = scores >= threshold
        tuned_matrix = confusion_matrix(labels, tuned_predictions, labels=[0, 1])
        tn, fp, fn, tp = tuned_matrix.ravel()
        tuned_cost = (fp + tp) * COST_REVIEW_EUR + fn * COST_MISSED_FAILURE_EUR
        print(f"\nOverall failure {label} (default threshold=0.50):")
        print(classification_report(labels, default_predictions, zero_division=0))
        print("Confusion matrix:")
        print(confusion_matrix(labels, default_predictions, labels=[0, 1]).tolist())
        print(f"ROC-AUC: {roc_auc_score(labels, scores):.4f}")
        print(f"\nCost-sensitive threshold: {threshold:.4f}")
        print(classification_report(labels, tuned_predictions, zero_division=0))
        print("Cost-sensitive confusion matrix:")
        print(tuned_matrix.tolist())
        print(
            "Cost-sensitive metrics: "
            f"recall={recall_score(labels, tuned_predictions, zero_division=0):.4f}, "
            f"precision={precision_score(labels, tuned_predictions, zero_division=0):.4f}, "
            f"f1={f1_score(labels, tuned_predictions, zero_division=0):.4f}, "
            f"cost={tuned_cost:.2f} EUR"
        )
        return {
            "roc_auc": round(float(roc_auc_score(labels, scores)), 4),
            "default_confusion_matrix": confusion_matrix(
                labels, default_predictions, labels=[0, 1]
            ).tolist(),
            "tuned_confusion_matrix": tuned_matrix.tolist(),
            "tuned_recall": round(
                float(recall_score(labels, tuned_predictions, zero_division=0)), 4
            ),
            "tuned_precision": round(
                float(precision_score(labels, tuned_predictions, zero_division=0)), 4
            ),
            "tuned_f1": round(
                float(f1_score(labels, tuned_predictions, zero_division=0)), 4
            ),
            "tuned_cost_eur": round(float(tuned_cost), 2),
        }

    validation_metrics = summarize(
        y_validation, validation_probabilities, "validation"
    )
    test_metrics = summarize(y_test, probabilities, "test")

    # APIan eta model_artifact-en gorde behar diren metrikak paketatu.
    metrics = {
        "roc_auc": test_metrics["roc_auc"],
        "default_confusion_matrix": test_metrics["default_confusion_matrix"],
        "tuned_confusion_matrix": test_metrics["tuned_confusion_matrix"],
        "tuned_threshold": round(threshold, 4),
        "cost_review_eur": COST_REVIEW_EUR,
        "cost_missed_failure_eur": COST_MISSED_FAILURE_EUR,
        "validation": validation_metrics,
        "test": test_metrics,
        **threshold_metrics,
    }
    return threshold, metrics


def main() -> None:
    """Entrenamenduaren workflow osoa exekutatu eta eredua diskoan gorde.

    Urrats nagusiak: CSVa egiaztatu eta irakurri, garbitu, feature engineering
    aplikatu, datuak banatu, hiru ereduak entrenatu, ebaluatu eta APIak kargatuko
    duen artifact-a sortu.
    """

    # Entrenamendu-fitxategia existitzen dela egiaztatu.
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Training data not found: {DATA_PATH}")

    # CSVa irakurri, garbitu eta feature engineering aplikatu.
    cleaned = add_engineered_features(clean_training_data(pd.read_csv(DATA_PATH)))
    # Ereduari emango zaizkion ezaugarri numeriko eta kategorikoen zerrendak.
    numeric_feature_columns = [*FEATURE_COLUMNS, *ENGINEERED_FEATURE_COLUMNS]
    feature_columns = [*numeric_feature_columns, QUALITY_COLUMN]
    # X sarrerako ezaugarriak dira; y hutsegite orokorraren benetako etiketa.
    X = cleaned[feature_columns]
    y = cleaned[TARGET_COLUMN].astype(int)
    # Hutsegite-mota bakoitza zutabe independente batean duen irteera anitzekoa.
    y_failure_types = cleaned[FAILURE_TYPE_COLUMNS].astype(int)

    # Lehenik %80 garapen-multzoa eta %20 azken test-multzoa bereizten ditugu.
    # Azken test-a ez da atalasea aukeratzeko erabiliko.
    (
        X_development,
        X_test,
        y_development,
        y_test,
        types_development,
        types_test,
    ) = train_test_split(
        X,
        y,
        y_failure_types,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )
    # Garapen-multzoaren %75 entrenatzeko eta %25 balidatzeko da; guztira
    # datasetaren %60/%20/%20 banaketa lortzen dugu.
    (
        X_train,
        X_validation,
        y_train,
        y_validation,
        types_train,
        types_validation,
    ) = train_test_split(
        X_development,
        y_development,
        types_development,
        test_size=0.25,
        random_state=42,
        stratify=y_development,
    )

    # 1) Hutsegite orokorra aurreikusten duen Random Forest gainbegiratua.
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
    # Pipeline barruan aurreprozesaketa eta sailkatzailea entrenatu.
    overall_model.fit(X_train, y_train)

    # 2) Hutsegite mota bakoitza (TWF, HDF,...) aurreikusten duen eredu anizkoitza.
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
    # MultiOutputClassifier-ek Random Forest bana entrenatzen du mota bakoitzeko.
    failure_type_model.fit(X_train, types_train)

    # 3) Isolation Forest: ohiko (failure=0) errenkadekin anomaliak ikasi.
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
    # Benetako hutsegiterik gabeko entrenamendu-errenkadak soilik erabili.
    normal_rows = X_train[y_train == 0]
    anomaly_model.fit(normal_rows)

    # Eredu nagusia ebaluatu eta ekoizpenean erabiliko den atalasea gorde.
    failure_threshold, evaluation_metrics = evaluate_failure_model(
        overall_model,
        X_validation,
        y_validation,
        X_test,
        y_test,
    )

    # Pipeline barruko Random Forest-era iritsi feature importance lortzeko.
    classifier = overall_model.named_steps["classifier"]
    print("Feature importance:")
    # OneHotEncoder-en ondoren geratzen diren zutabeen izenak berreskuratu.
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

    # Hutsegite mota bakoitzaren balidazio-txostena inprimatu.
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

    # IsolationForest-ek -1 ematen du anomalia eta 1 ohiko datua denean.
    anomaly_flags = anomaly_model.predict(X_test) == -1
    print("\nIsolationForest anomaly validation:")
    print(classification_report(y_test, anomaly_flags, zero_division=0))

    # APIak abioan kargatuko duen objektu bakarrean ereduak, ezaugarriak,
    # atalasea eta ebaluazio-metrikak bildu.
    model_artifact = {
        # Bertsio berria: kostu bidezko atalasea eta validation/test ebaluazioa.
        "version": 4,
        "overall_model": overall_model,
        "failure_type_model": failure_type_model,
        "anomaly_model": anomaly_model,
        "feature_columns": feature_columns,
        "engineered_feature_columns": ENGINEERED_FEATURE_COLUMNS,
        "failure_type_columns": FAILURE_TYPE_COLUMNS,
        "failure_threshold": failure_threshold,
        "costs": {
            "review_eur": COST_REVIEW_EUR,
            "missed_failure_eur": COST_MISSED_FAILURE_EUR,
        },
        "evaluation": evaluation_metrics,
        "quality_values": {"H": "High", "M": "Medium", "L": "Low"},
    }

    # ``models`` karpeta sortu ez badago eta artifact-a pickle bidez gorde.
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_artifact, MODEL_PATH)
    print(f"Model saved to: {MODEL_PATH}")


if __name__ == "__main__":
    main()
