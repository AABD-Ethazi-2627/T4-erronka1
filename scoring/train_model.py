"""Clean the training CSV, train the failure models, and save them for the API."""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report
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


def _make_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", FEATURE_COLUMNS),
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


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Training data not found: {DATA_PATH}")

    cleaned = clean_training_data(pd.read_csv(DATA_PATH))
    feature_columns = [*FEATURE_COLUMNS, QUALITY_COLUMN]
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
            ("preprocessor", _make_preprocessor()),
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
            ("preprocessor", _make_preprocessor()),
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
            ("preprocessor", _make_preprocessor()),
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

    print("\nOverall failure validation:")
    print(classification_report(y_test, overall_model.predict(X_test), zero_division=0))

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
        "version": 2,
        "overall_model": overall_model,
        "failure_type_model": failure_type_model,
        "anomaly_model": anomaly_model,
        "feature_columns": feature_columns,
        "failure_type_columns": FAILURE_TYPE_COLUMNS,
        "quality_values": {"H": "High", "M": "Medium", "L": "Low"},
    }

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_artifact, MODEL_PATH)
    print(f"Model saved to: {MODEL_PATH}")


if __name__ == "__main__":
    main()
