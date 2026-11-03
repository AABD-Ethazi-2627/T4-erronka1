"""Offline entrenamenduaren taulak, PNG grafikoak eta HTML txostena sortu.

train_model.py-k eta notebookak funtzio hauek partekatzen dituzte. Atalasea
balidazioan hautatzen da; testeko emaitzak azken neurketa independentea dira.
"""

import base64
from html import escape
from pathlib import Path

import matplotlib

# Zerbitzariak ez du leiho grafikorik behar: grafikoak fitxategietan gordetzen dira.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay, PrecisionRecallDisplay, RocCurveDisplay,
    accuracy_score, average_precision_score, classification_report,
    confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


SENSORS = ["air_temp_K", "process_temp_K", "rpm", "torque_Nm", "tool_wear_min"]
FEATURES = [*SENSORS, "temp_diff", "power_est"]
TYPES = ["TWF", "HDF", "PWF", "OSF", "RNF"]
LABELS = {
    "air_temp_K": "Airearen tenperatura (K)",
    "process_temp_K": "Prozesuaren tenperatura (K)",
    "rpm": "Biraketa-abiadura (RPM)",
    "torque_Nm": "Torquea (Nm)",
    "tool_wear_min": "Erremintaren higadura (min)",
    "temp_diff": "Tenperatura-aldea (K)",
    "power_est": "Potentziaren adierazlea (RPM × Nm)",
}
REPORT_NAMES = {"precision": "Doitasuna", "recall": "Recall", "f1-score": "F1", "support": "Adibideak"}


def _figure(fig, directory: Path, name: str) -> None:
    """Irudiaren ertzak egokitu, PNGan gorde eta memoria askatu."""
    fig.tight_layout()
    fig.savefig(directory / name, dpi=125, bbox_inches="tight")
    plt.close(fig)


def _csv(table: pd.DataFrame, directory: Path, name: str) -> None:
    """Datu numerikoak CSV gisa esportatu, kalkulu berrietarako erabilgarri."""
    table.to_csv(directory / name, index=False, encoding="utf-8-sig")


def create_eda(data: pd.DataFrame, report_dir: Path) -> None:
    """Klaseen desoreka, sentsoreen banaketak eta erlazioak erakutsi."""
    report_dir.mkdir(parents=True, exist_ok=True)
    _csv(data[FEATURES].describe().T.rename_axis("Aldagaia").reset_index(), report_dir, "estatistikak.csv")
    counts = data["machine_failure"].value_counts().reindex([0, 1], fill_value=0)
    classes = pd.DataFrame({"Klasea": ["Hutsegiterik ez", "Hutsegitea"], "Adibideak": counts.to_numpy()})
    classes["Ehunekoa (%)"] = classes["Adibideak"] / len(data) * 100
    _csv(classes, report_dir, "klaseen_banaketa.csv")

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    axes[0].bar(classes["Klasea"], counts, color=["#2E7D32", "#D32F2F"])
    axes[0].set(title="Helburuaren desoreka", ylabel="Irakurketa kopurua")
    for index, count in enumerate(counts):
        axes[0].text(index, count, f"{count}\n({count / len(data):.1%})", ha="center", va="bottom")
    axes[0].set_ylim(0, max(counts) * 1.23)
    quality = data["machine_type"].value_counts().reindex(["L", "M", "H"], fill_value=0)
    axes[1].bar(["L: baxua", "M: ertaina", "H: altua"], quality, color="#247BA0")
    axes[1].set(title="Makinaren kalitate-maila", ylabel="Irakurketa kopurua")
    type_counts = data[[f"failure_{name}" for name in TYPES]].sum()
    axes[2].bar(TYPES, type_counts, color="#9170B8")
    axes[2].set(title="Benetako hutsegite-motak", ylabel="Etiketa positiboak")
    _figure(fig, report_dir, "eda_klaseak.png")

    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    for ax, column in zip(axes.flat, SENSORS):
        ax.hist(data[column], bins=35, color="#247BA0", edgecolor="white")
        ax.set(xlabel=LABELS[column], ylabel="Irakurketa kopurua")
    axes.flat[-1].set_visible(False)
    fig.suptitle("Sentsoreen balioen banaketa")
    _figure(fig, report_dir, "eda_histogramak.png")

    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    for ax, column in zip(axes.flat, SENSORS):
        ax.boxplot([data.loc[data.machine_failure == label, column] for label in [0, 1]],
                   tick_labels=["Hutsegiterik ez", "Hutsegitea"], showfliers=False)
        ax.set(ylabel=LABELS[column])
    axes.flat[-1].set_visible(False)
    fig.suptitle("Sentsoreak benetako klasearen arabera (muturreko puntuak ezkutatuta)")
    _figure(fig, report_dir, "eda_klaseen_alderaketa.png")

    columns = [*FEATURES, "machine_failure"]
    correlation = data[columns].corr()
    fig, ax = plt.subplots(figsize=(10, 8))
    image = ax.imshow(correlation, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(columns)), columns, rotation=45, ha="right")
    ax.set_yticks(range(len(columns)), columns)
    for row in range(len(columns)):
        for col in range(len(columns)):
            ax.text(col, row, f"{correlation.iloc[row, col]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title("Korrelazio linealak: erlazioa ez da kausalitatea")
    fig.colorbar(image, ax=ax, label="Pearson korrelazioa")
    _figure(fig, report_dir, "eda_korrelazioak.png")


def _metrics(y_true, probabilities, threshold: float, costs: dict) -> dict:
    """Atalase jakin batean sailkapen-metrikak eta kostu esleitua kalkulatu."""
    predictions = np.asarray(probabilities) >= threshold
    tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    return {
        "Atalasea": threshold,
        "Accuracy": accuracy_score(y_true, predictions),
        "Recall": recall_score(y_true, predictions, zero_division=0),
        "Doitasuna": precision_score(y_true, predictions, zero_division=0),
        "F1": f1_score(y_true, predictions, zero_division=0),
        "ROC-AUC": roc_auc_score(y_true, probabilities),
        "AP": average_precision_score(y_true, probabilities),
        "TN": int(tn), "FP": int(fp), "FN": int(fn), "TP": int(tp),
        "Kostua (EUR)": float(tn * costs["true_negative_eur"] + fp * costs["false_positive_eur"]
                              + fn * costs["false_negative_eur"] + tp * costs["true_positive_eur"]),
    }


def _classification(y_true, predictions) -> pd.DataFrame:
    """Classification report-a euskarazko goiburuak dituen taula bihurtu."""
    report = classification_report(y_true, predictions, labels=[0, 1],
                                   target_names=["Hutsegiterik ez", "Hutsegitea"],
                                   output_dict=True, zero_division=0)
    return (pd.DataFrame({key: value for key, value in report.items() if isinstance(value, dict)}).T
            .rename(columns=REPORT_NAMES).rename_axis("Klasea").reset_index())


def create_training_report(data, artifact, X_train, y_train, X_validation, y_validation,
                           X_test, y_test, types_test, *, report_dir: Path) -> None:
    """Eredu berberen balidazioa eta test independentea dokumentatu."""
    report_dir = Path(report_dir)
    create_eda(data, report_dir)
    rf = artifact["overall_model"]
    threshold = artifact["failure_threshold"]
    costs = artifact["costs"]
    val_probability = rf.predict_proba(X_validation)[:, 1]
    test_probability = rf.predict_proba(X_test)[:, 1]
    test_prediction = test_probability >= threshold

    # Erreferentzia lineala eskalatuta entrenatu, magnitudeek optimizazioa ez desorekatzeko.
    logistic = Pipeline([
        ("preprocessor", clone(rf.named_steps["preprocessor"])),
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(class_weight="balanced", max_iter=3000, random_state=42)),
    ])
    logistic.fit(X_train, y_train)
    comparisons = []
    for name, probability, cutoff in [
        ("Beti hutsegiterik ez", np.zeros(len(y_validation)), 0.5),
        ("Erregresio logistikoa", logistic.predict_proba(X_validation)[:, 1], 0.5),
        ("Random Forest (0,50)", val_probability, 0.5),
        ("Random Forest (atalase doitua)", val_probability, threshold),
    ]:
        comparisons.append({"Eredua": name, **_metrics(y_validation, probability, cutoff, costs)})
    comparison = pd.DataFrame(comparisons)
    _csv(comparison, report_dir, "ereduen_konparazioa.csv")
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    positions = np.arange(len(comparison))
    for offset, metric, color in [(-0.25, "Recall", "#247BA0"), (0, "Doitasuna", "#E6A700"), (0.25, "F1", "#2E7D32")]:
        axes[0].bar(positions + offset, comparison[metric], width=0.24, label=metric, color=color)
    axes[0].set_xticks(positions, comparison.Eredua, rotation=20, ha="right", fontsize=8)
    axes[0].set(ylim=(0, 1.08), title="Balidazioko ereduen alderaketa", ylabel="Metrika (0–1)")
    axes[0].legend()
    axes[1].bar(positions, comparison["Kostua (EUR)"], color="#D32F2F")
    axes[1].set_xticks(positions, comparison.Eredua, rotation=20, ha="right", fontsize=8)
    axes[1].set(title="Balidazioko kostu esleitua", ylabel="Kostua (€)")
    _figure(fig, report_dir, "ereduen_konparazioa.png")

    # Testa behin ebaluatu: atalasea aurretik balidazioan hautatu da.
    results = []
    for name, truth, probability in [("Balidazioa", y_validation, val_probability), ("Test independentea", y_test, test_probability)]:
        for cutoff in [0.5, threshold]:
            results.append({"Multzoa": name, **_metrics(truth, probability, cutoff, costs)})
    _csv(pd.DataFrame(results), report_dir, "metrikak.csv")
    _csv(_classification(y_test, test_prediction), report_dir, "classification_report.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, cutoff, title in zip(axes, [0.5, threshold], ["Ohiko atalasea: 0,50", f"Balidazioan hautatua: {threshold:.3f}"]):
        ConfusionMatrixDisplay(confusion_matrix(y_test, test_probability >= cutoff, labels=[0, 1]),
                               display_labels=["Hutsegiterik ez", "Hutsegitea"]).plot(ax=ax, cmap="Blues", colorbar=False)
        ax.set(title=title, xlabel="Aurreikusitako klasea", ylabel="Benetako klasea")
    fig.suptitle("Test independentearen nahasmen-matrizeak: goian TN/FP, behean FN/TP")
    _figure(fig, report_dir, "nahasmen_matrizeak.png")

    # Kurba hau BALIDAZIOAN kalkulatzen da. Ez da testa erabiltzen atalasea aukeratzeko.
    candidates = np.unique(np.r_[0.0, val_probability, 1.0])
    curve = pd.DataFrame([_metrics(y_validation, val_probability, cutoff, costs) for cutoff in candidates])
    _csv(curve, report_dir, "atalase_kurba.csv")
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    axes[0].plot(curve.Atalasea, curve["Kostua (EUR)"], color="#D32F2F")
    axes[0].set(title="Balidazioaren kostu-kurba", xlabel="Erabaki-atalasea", ylabel="Kostu esleitu osoa (€)")
    axes[1].plot(curve.Atalasea, curve.Recall, label="Recall")
    axes[1].plot(curve.Atalasea, curve.Doitasuna, label="Doitasuna")
    axes[1].axhline(artifact["evaluation"]["target_recall"], color="grey", linestyle=":", label="Recall helburua")
    axes[1].set(title="Atalasearen eta detekzioaren arteko oreka", xlabel="Erabaki-atalasea", ylabel="Metrika (0–1)")
    axes[1].legend()
    for ax in axes:
        ax.axvline(threshold, color="black", linestyle="--", label="Atalase hautatua")
        ax.grid(alpha=0.2)
    _figure(fig, report_dir, "atalase_kostua.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    RocCurveDisplay.from_predictions(y_test, test_probability, ax=axes[0], name="Random Forest")
    axes[0].plot([0, 1], [0, 1], "--", color="grey")
    axes[0].set(title="Testeko ROC kurba", xlabel="Alarma faltsuen tasa", ylabel="Recall")
    PrecisionRecallDisplay.from_predictions(y_test, test_probability, ax=axes[1], name="Random Forest")
    axes[1].axhline(y_test.mean(), linestyle="--", color="grey", label="Hutsegiteen proportzioa")
    axes[1].set(title="Testeko Recall–Doitasuna kurba", xlabel="Recall", ylabel="Doitasuna")
    _figure(fig, report_dir, "roc_pr_kurbak.png")

    feature_names = rf.named_steps["preprocessor"].get_feature_names_out()
    importance = pd.DataFrame({"Aldagaia": feature_names, "Garrantzia": rf.named_steps["classifier"].feature_importances_})
    importance = importance.sort_values("Garrantzia", ascending=False)
    _csv(importance, report_dir, "aldagaien_garrantzia.csv")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(importance.Aldagaia.iloc[::-1], importance.Garrantzia.iloc[::-1], color="#247BA0")
    ax.set(title="Random Forest: aldagaien garrantzia (ez da kausalitatea)", xlabel="Garrantzi erlatiboa")
    _figure(fig, report_dir, "aldagaien_garrantzia.png")

    type_predictions = artifact["failure_type_model"].predict(X_test)
    type_results = []
    for index, name in enumerate(TYPES):
        truth, predicted = types_test.iloc[:, index], type_predictions[:, index]
        type_results.append({"Mota": name, "Benetako kasuak": int(truth.sum()),
                             "Recall": recall_score(truth, predicted, zero_division=0),
                             "Doitasuna": precision_score(truth, predicted, zero_division=0),
                             "F1": f1_score(truth, predicted, zero_division=0)})
    _csv(pd.DataFrame(type_results), report_dir, "hutsegite_motak.csv")
    fig, ax = plt.subplots(figsize=(9, 4))
    pd.DataFrame(type_results).set_index("Mota")[["Recall", "Doitasuna", "F1"]].plot.bar(ax=ax, color=["#247BA0", "#E6A700", "#2E7D32"])
    ax.set(title="Testeko hutsegite-moten emaitzak (atalase lehenetsiak)", ylabel="Metrika (0–1)", ylim=(0, 1.1))
    _figure(fig, report_dir, "hutsegite_motak.png")

    anomaly = artifact["anomaly_model"]
    scores = anomaly.decision_function(X_test)
    anomaly_flags = anomaly.predict(X_test) == -1
    _csv(_classification(y_test, anomaly_flags), report_dir, "anomalia_vs_hutsegitea.csv")
    fig, ax = plt.subplots(figsize=(10, 4))
    for label, text, color in [(0, "Benetan hutsegiterik ez", "#2E7D32"), (1, "Benetako hutsegitea", "#D32F2F")]:
        ax.hist(scores[np.asarray(y_test) == label], bins=30, density=True, alpha=0.55, label=text, color=color)
    ax.axvline(0, color="black", linestyle="--", label="Anomalia-muga: 0")
    ax.set(title="Isolation Forest: balio negatiboak anomalitzat hartzen dira", xlabel="decision_function puntuazioa (ez da probabilitatea)", ylabel="Dentsitatea")
    ax.legend()
    _figure(fig, report_dir, "anomaliak.png")

    # Etiketa errealak ebaluaziorako soilik erabiltzen dira, inoiz ez X sarreran.
    predictions = data.loc[X_test.index, [*SENSORS, "machine_type", "machine_failure"]].copy()
    predictions["Arriskua (%)"] = test_probability * 100
    predictions["Iragarpena"] = test_prediction.astype(int)
    predictions["Emaitza"] = np.select([
        (np.asarray(y_test) == 1) & test_prediction,
        (np.asarray(y_test) == 0) & test_prediction,
        (np.asarray(y_test) == 1) & ~test_prediction], ["TP", "FP", "FN"], default="TN")
    outcome_costs = {"TP": costs["true_positive_eur"], "TN": costs["true_negative_eur"],
                     "FP": costs["false_positive_eur"], "FN": costs["false_negative_eur"]}
    predictions["Kostua (EUR)"] = predictions.Emaitza.map(outcome_costs)
    predictions["Anomalia"] = anomaly_flags
    predictions["Anomalia puntuazioa"] = scores
    _csv(predictions.rename_axis("CSV errenkada").reset_index(), report_dir, "test_iragarpenak.csv")
    _csv(predictions[predictions.Emaitza.isin(["FP", "FN"])].rename_axis("CSV errenkada").reset_index(), report_dir, "akatsak_fp_fn.csv")
    economic = pd.DataFrame({"Emaitza": ["TN", "FP", "FN", "TP"]})
    economic["Kopurua"] = economic.Emaitza.map(predictions.Emaitza.value_counts()).fillna(0).astype(int)
    economic["Kasuaren kostua (EUR)"] = economic.Emaitza.map(outcome_costs)
    economic["Kostu osoa (EUR)"] = economic.Kopurua * economic["Kasuaren kostua (EUR)"]
    _csv(economic, report_dir, "kostuen_banaketa.csv")
    _write_html(report_dir, threshold, artifact["evaluation"]["target_recall"])


def _write_html(directory: Path, threshold: float, recall_target: float) -> None:
    """PNGak HTMLan txertatu: txostena fitxategi bakarrarekin ireki daiteke."""
    sections = [
        ("2. EDA eta klaseen desoreka", ["klaseen_banaketa.csv", "estatistikak.csv"], ["eda_klaseak.png", "eda_histogramak.png", "eda_klaseen_alderaketa.png", "eda_korrelazioak.png"]),
        ("5. Ereduen konparazioa (balidazioa)", ["ereduen_konparazioa.csv"], ["ereduen_konparazioa.png"]),
        ("6. Atalasea balidazioan aukeratzea", [], ["atalase_kostua.png"]),
        ("6. Test independentearen ebaluazioa", ["metrikak.csv", "classification_report.csv", "kostuen_banaketa.csv"], ["nahasmen_matrizeak.png", "roc_pr_kurbak.png"]),
        ("7. Aldagaien garrantzia", ["aldagaien_garrantzia.csv"], ["aldagaien_garrantzia.png"]),
        ("8. Hutsegite-motak eta anomaliak", ["hutsegite_motak.csv", "anomalia_vs_hutsegitea.csv"], ["hutsegite_motak.png", "anomaliak.png"]),
        ("9. FP eta FN kasuen adibideak (lehen 10ak)", ["akatsak_fp_fn.csv"], []),
    ]
    html = ["<!doctype html><html lang='eu'><meta charset='utf-8'><title>CNC: entrenamenduaren ebaluazioa</title>",
            "<style>body{font-family:system-ui;max-width:1350px;margin:40px auto;padding:0 24px;color:#172b4d}img{max-width:100%;height:auto}table{border-collapse:collapse;font-size:13px}td,th{padding:8px;border:1px solid #ddd;text-align:right}.table{overflow-x:auto}h2{margin-top:50px}p{line-height:1.6}</style>",
            "<h1>CNC: offline entrenamendua eta ebaluazioa</h1>",
            f"<p>Atalase hautatua: {threshold:.4f}. Balidazioko Recall helburua: {recall_target:.0%}. Banaketa: %60 entrenamendua, %20 balidazioa, %20 testa.</p>",
            "<p>Recall = TP/(TP+FN); doitasuna = TP/(TP+FP). Accuracy altuak hutsegiteak ezkutatu ditzake, klaseak desorekatuta daudelako. Kostuak: FN 5.000 €, FP 200 €, TP 300 €, TN 0 €. Kostuak snapshot bakoitzeko simulazioak dira; ez dira benetako fakturak.</p>",
            "<p>Arriskua Random Forest-en probabilitate estimatua da, kalibratu gabea. Anomalia Isolation Forest-en ezohiko portaera da, eta ez du berez hutsegitea frogatzen. Haren puntuazioa ez da probabilitatea. RNF ausazkoa denez, sentsore hauekin aurreikusteko gaitasuna mugatua da.</p>",
            "<p>Datuak uneko snapshot-ak dira: ez da hutsegitearen etorkizuneko ordua aurreikusten. timestamp eta machine_id ez dira entrenamendu-aldagaiak. power_est = RPM × Nm adierazle proportzionala da; wattak lortzeko 2π/60 faktorea behar da. Aldagaien garrantziak eta korrelazioek ez dute kausalitatea frogatzen.</p>"]
    for title, tables, figures in sections:
        html.append(f"<h2>{escape(title)}</h2>")
        for name in tables:
            table = pd.read_csv(directory / name)
            if name == "akatsak_fp_fn.csv":
                table = table.head(10)
            html.append("<div class='table'>" + table.to_html(index=False, float_format=lambda value: f"{value:.4f}") + "</div>")
        for name in figures:
            encoded = base64.b64encode((directory / name).read_bytes()).decode("ascii")
            html.append(f"<img alt='{escape(title)}' src='data:image/png;base64,{encoded}'>")
    html.append("</html>")
    (directory / "txostena.html").write_text("\n".join(html), encoding="utf-8")
