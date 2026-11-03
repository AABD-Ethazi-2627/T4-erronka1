# Offline entrenamendua eta ebaluazio bisuala

`02_training.ipynb` notebookak EDA, ereduen alderaketa, Recall/Doitasuna/F1,
test independentearen nahasmen-matrizeak, kostu-kurba, aldagaien garrantzia,
hutsegite-motak eta anomalien azterketa ditu. Irteerak notebookean txertatzen dira.

## Notebooka ireki edo berriz exekutatu

VS Coden ireki `02_training.ipynb`, aukeratu `.venv` kernel gisa eta sakatu
**Run All**. Amaitzean gorde fitxategia, irteerak entregagaian ager daitezen.

Terminaletik exekutatzeko, proiektuaren errotik:

```powershell
.\.venv\Scripts\python.exe -m pip install -r scoring\requirements-notebook.txt
.\.venv\Scripts\python.exe notebooks\execute_training.py
```

Notebookak txostenak sortzen ditu baina ez du ekoizpeneko `.pkl`-a ordezkatzen.

## Eredua entrenatu eta gorde

```powershell
.\.venv\Scripts\python.exe scoring\train_model.py
```

Komando horrek eredu-paketea `models/cnc_failure_model.pkl`-n gordetzen du eta,
gainera, `reports/training/txostena.html`, PNGak eta CSVak sortzen ditu.
HTML txostena nabigatzailean ireki daiteke; irudiak barruan txertatuta ditu.

Eredua ordezkatu gabe ebaluatzeko:

```powershell
.\.venv\Scripts\python.exe scoring\train_model.py --no-save-model
```

Atalasea balidazioan hautatzen da (%20); azken emaitza test independentean
neurtzen da (%20); gainerako %60 entrenamendurako da. CSVko 8.000 irakurketak
datuen garapen- eta ebaluazio-prozesuan banatzen dira; ez dira 8.000ak batera
eredua doitzen erabiltzen.

## Emaitzak interpretatzea

- Recall: benetako hutsegiteen artean atzemandako proportzioa.
- Doitasuna: hutsegite-abisuen artean zuzenak diren proportzioa.
- Kostu esleitua: FN × 5.000 € + FP × 200 € + TP × 300 € + TN × 0 €.
- Arriskua: Random Forest-en probabilitate estimatua, kalibratu gabea.
- Anomalia: Isolation Forest-ek ezohikotzat jotako irakurketa; ez da hutsegitearen froga.
- KONTUZ: atalase ekonomikoa gainditu da edo anomalia dago. TP/FP/FN/TN,
  aldiz, `failure_predicted` erabakiaren arabera kalkulatzen dira.

Kostuak snapshot bakoitzeko simulazioak dira. Benetako gastuak neurtzeko,
matxura edo esku-hartze bakoitzaren identifikatzailea behar da.
