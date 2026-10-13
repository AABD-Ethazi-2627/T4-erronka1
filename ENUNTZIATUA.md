# Erronka 1 — CNC Guard: Mantentze Prediktiboa

**IABD Espezializazioa · 5071, 5072, 5073, 5074, 5075 moduluak**
**Iraupena: ~3 aste · ~45 ordu**

---

## Testuingurua eta Erronka

**ARAKAIN Makineriak** 50 CNC makina ditu Bilboko fabrika batean. Makina bakoitza gelditzen
denean, produkzioa eteten da — eta kostua **1.200 €/orduko** da.

Orain arte mantentze-lanak honela egiten ziren: makina hautsi, gelditu, konpondu. Honi
**mantentze korrektiboa** esaten zaio. Enpresaren helburua aldatzea da: hutsegitea gertatu
**aurretik** jakitea, eta aurrea hartzea.

Zure taldeak, Big Data eta IA ingeniari gisa, sistema bat eraiki behar du:

1. Makinetako sentsore-datuak **denbora errealean** bildu eta biltegiratu
2. Datu historikoetatik **eredu bat entrenatu** hutsegiteak iragartzeko
3. Eredu hori **ekoizpen-sisteman txertatu** alerta automatikoak sortzeko

---

## Datua

**AI4I 2020 Predictive Maintenance Dataset** — UCI Machine Learning Repository
Lizentzia: CC BY 4.0

| Ezaugarria | Balioa |
|---|---|
| Errenkada kopurua | 10.000 (zuk 8.000 erabiliko dituzu entrenamendurako) |
| Ezaugarri kopurua | 13 + helburua |
| Hutsegite-tasa | %3,4 (klase-inoreka!) |

**Zutabeak:**

| Zutabea | Deskribapena | Unitatea |
|---|---|---|
| `machine_id` | Makinaren identifikadorea | CNC-001..050 |
| `machine_type` | Makinaren mota | H / M / L |
| `air_temp_K` | Inguruko tenperatura | Kelvin |
| `process_temp_K` | Prozesuko tenperatura | Kelvin |
| `rpm` | Errotazio-abiadura | birak/min |
| `torque_Nm` | Torkea | Newton·metro |
| `tool_wear_min` | Tresna-higadura | minutu |
| `machine_failure` | **Helburua**: hutsegitea gertatu da? | 0 / 1 |
| `failure_TWF/HDF/PWF/OSF/RNF` | Hutsegite motaren azpimultzoak | 0 / 1 |

> **Kontuz:** Entrenamendurako `ai4i2020_train.csv` fitxategia soilik erabili behar duzu.
> Simuladoreak test datuak erabiltzen ditu — ez nahastu!

---

## Starter Kit-a

Irakasleak Docker-ekin prest dagoen ingurunea ematen dizu. VM-an exekutatu:

```bash
cd ~/cnc-guard
docker compose up -d --build
docker compose ps
```

Zerbitzu hauek abiarazten dira:

| Zerbitzua | Helburua | URLa |
|---|---|---|
| **Filebeat** | Simuladorearen CSV-ak irakurri, Kafka-ra produzitu | — |
| **Apache Kafka** | Datu-bufferra eta desakoplaketa (KRaft mode) | kafka:9092 (sare barnetik) |
| **Apache NiFi** | Datuen transformazioa eta bideratzea | https://localhost:8443 |
| **Elasticsearch** | Biltegiratze eta bilaketa | http://localhost:9200 |
| **Kibana** | Bistaratzea eta dashboardak | http://localhost:5601 |
| **scoring-api** | ML inferentzia (3. fasean erabiliko duzu) | http://localhost:8000/docs |

> **NiFi sarbidea:** erabiltzailea `admin`, pasahitza `adminpassword123`

Simuladorea irakasleak martxan jartzen du zerbitzari nagusian. Zure VM-ak NFS bidez
jasotzen ditu CSV fitxategiak `/mnt/cnc-stream/` karpetan.

---

## Arkitektura: Zure Lan-Mapa

---

## 1. Fasea — Sentsore-Datuak Hartu eta Gorde

### Helburua

Makinetako sentsore-datuak denbora errealean bildu, Elasticsearch-en biltegiratu, eta
Kibana-n bistaratu, fabrikako makineria-egoeraren ikuspegi osoa edukitzeko.

### Zure Zeregina 1: Filebeat Konfiguratu

`filebeat/filebeat.yml` fitxategia eskeletoa da — zuk osatu behar duzu.

> **Pista:** Docker Compose-en zerbitzu-izenak hostname gisa funtzionatzen dute sare
> barnean. `docker-compose.yml`-eko zerbitzu-izenak begiratu.

Aldaketak aplikatzeko:
```bash
docker compose restart filebeat
docker logs cnc-filebeat   # Erroreak ikusten diren egiaztatu
```

### Zure Zeregina 2: NiFi Flow Osatu

NiFi-k Kafka Topicetik lerro bakoitza FlowFile bat gisa jasotzen du. Lerro baten itxura:

```
2026-04-29T10:57:50Z,CNC-039,L,299.0,308.6,1587,38.6,124,0,0,0,0,0,0
```

NiFi flow bat osatu behar duzu.


### Kibana Dashboarda

Sortu dashboard bat honako bista-motekin:

- **Line chart:** tenperatura bilakaera denboran zehar (makina bakoitzeko)
- **Heatmap:** tresna-higadura vs hutsegite-maiztasuna
- **Data table:** azken 50 gertaeren laburpena
- **KPI cards:** hutsegite-tasa orokorra eta makina aktiboen kopurua

### 💬 Pentsatzeko Galderak — 1. Fasea

> Galdera hauek ez dira ebaluatu behar diren ariketak — pentsatzeko eta taldean eztabaidatzeko dira.

**G1.** Filebeat-ek fitxategien jarraipena registry batean gordetzen du — badaki zer
lerro irakurri duen jada. Zer gertatuko litzateke Filebeat berrabiaraziko bagenu registry
gabe? Eta NiFi-k zuzenean irakurriko balu fitxategiak, nola kudeatuko luke "zer irakurri
dudan jada" arazoa?

**G2.** NFS esportazioa `read-only` konfiguratuta dago. Zergatik? Zer gertatuko litzateke
idazketa-baimena izango balu eta ikasle batek NiFi-n `GetFile` prozesadorea erabiliko balu
(fitxategiak ezabatzen dituena)?

**G3.** `exclude_lines` erregela bat idatzi duzu goiburu-lerroak iragazteko. Zer gertatuko
litzateke iragazketa hori ez egongo balitz eta goiburua Elasticsearch-era iritsiko balitz?
(Pentsatu: datu-motetan zer arazo sor liteke.)

**G4.** Kibana dashboard-a enpresako zuzendariei erakutsi behar diezu. Zer hiru KPI
izango lirateke garrantzitsuenak? Zergatik?

### Entregablea — 1. Fasea

- [ ] `filebeat/filebeat.yml` osatuta eta funtzionala
- [ ] NiFi flow funtzionala (`.json` exportatua)
- [ ] Elasticsearch `cnc-sensors` indizea sortuta eta datuak barruan
- [ ] Kibana dashboard-aren screenshot-ak (4 bistaratzeekin)
- [ ] README laburra: zer datu dauden, nola antolatuta, eta pipeline-aren azalpena

---

## 2. Fasea — Preprocessing eta Entrenamendua (Offline)

**Iraupena:** ~1,5 aste | **Moduluak:** 5071 + 5072 + 5073 | **Pisua:** %40

### Helburua

Datu historikoetatik eredu bat entrenatu hutsegiteak iragarriko dituena. Eredua `.pkl`
fitxategi gisa gordetzen da 3. fasean scoring-api-k erabiltzeko.

### Zer Egin

`notebooks/02_training_TEMPLATE.ipynb` notebook-a oinarri gisa erabiliz:

**1. urratsa — Datu-karga eta azterketa**
```python
import pandas as pd
df = pd.read_csv('../data/ai4i2020_train.csv')
# Aztertu: df.info(), df.describe(), df['machine_failure'].value_counts()
```

**2. urratsa — Klase-inoreka ulertu eta tratatu**

Hutsegiteak gutxiengoa dira (%3,4 soilik). Hau arazo larria da eredua entrenatzeko.
Aukeratu ikuspegietan bat eta **justifikatu** zergatik:
- `class_weight='balanced'` parametroa
- SMOTE gainmuestratzea (`imbalanced-learn` liburutegia)
- Atalase-doiketa (`threshold`)

**3. urratsa — Feature engineering (aukerakoa, puntu gehigarria)**
```python
df['temp_diff']  = df['process_temp_K'] - df['air_temp_K']
df['power_est']  = df['rpm'] * df['torque_Nm']
```

**4. urratsa — Entrenamendua**
```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

X = df[['air_temp_K', 'process_temp_K', 'rpm', 'torque_Nm', 'tool_wear_min']]
y = df['machine_failure']

X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)
model.fit(X_train, y_train)

print(classification_report(y_val, model.predict(X_val)))
```

**5. urratsa — Eredua gorde**
```python
import joblib
joblib.dump(model, '../models/cnc_failure_model.pkl')
print("Eredua gordeta!")
```

Gordeta dagoenean, scoring-api automatikoki kargatuko du:
```bash
docker compose restart scoring-api
curl http://localhost:8000/health  # "model_loaded": true ikusi behar da
```

### Ebaluazio-irizpideak — 2. Fasea

| Irizpidea | Pisua |
|---|---|
| Preprocessing urratsak justifikatuak (zergatik?) | %30 |
| Klase-inoreka modu egokian kudeatu | %25 |
| Metrikak egoki aukeratu eta interpretatu (recall > precision) | %25 |
| Kode dokumentatua eta irakurgarria | %20 |

> **Oharra:** Recall maximizatzea lehenesten da precision-en gainetik. Enpresarentzat
> hutsegite bat ez iragartzea (**false negative**) askoz kaltegarriagoa da alerta faltso
> bat (**false positive**) baino. Pentsatu: 1.200 €/orduko makina bat gelditzearen kostua
> vs. alerta faltso batek eragindako mantentze-bisita baten kostua.

### 💬 Pentsatzeko Galderak — 2. Fasea

**G5.** Datu-multzoaren %3,4 soilik dira hutsegiteak. Zer gertatzen da eredua **accuracy**
bidez soilik ebaluatzen badugu? Zer puntuazio lortuko luke eredu batek beti "0" (ez da
huts egingo) iragarriko balu? Zergatik da hau arazo larria?

**G6.** Recall eta precision arteko trade-off-a: recall maximizatuz gero, precision jaisten
da. Zer esan nahi du honek praktikan ARAKAIN Makineriarentzat? Non dago oreka
egokia?

**G7.** `feature_importances_` atributua erabiliz jakin dezakezu zein ezaugarri den
garrantzitsuena. Zer espero zenuke? Bat dator zure intuitzioarekin? (`model.feature_importances_`)

**G8.** Entrenamenduan erabili den datua (`ai4i2020_train.csv`) eta simuladoreak
erabiltzen duena (`ai4i2020_test.csv`) jatorrizko dataset beretik etorri dira. Zergatik da
garrantzitsua data leakage ekiditea, hau da, test datuak entrenamenduan ez erabiltzea?

### Entregablea — 2. Fasea

- [ ] `notebooks/02_training.ipynb` osatua eta dokumentatua
- [ ] Confusion matrix eta classification report azalpenekin
- [ ] `models/cnc_failure_model.pkl` gordeta
- [ ] `curl http://localhost:8000/health` → `"model_loaded": true`

---

## 3. Fasea — Denbora Errealeko Inferentzia

**Iraupena:** ~0,5 aste | **Moduluak:** Guztiak (integrazioa) | **Pisua:** %25

### Helburua

Entrenatutako eredua ekoizpen-sisteman txertatu: Filebeat-ek datuak jasotzen ditu,
NiFi-k scoring-api-ra bidaltzen ditu, eta Kibana-n alerta bisualak sortzen dira
denbora errealean.

### Zer Gertatu Behar da

```
Filebeat → Kafka → NiFi → scoring-api (FastAPI) → NiFi → Elasticsearch → Kibana alertak
                           ↑
                       model.pkl (2. fasetik)
```

### Zure Zeregina: Scoring API-a Osatu (FastAPI)

`scoring/score_api.py` fitxategian eskeletoa daukazu. Zure lana da FastAPI zerbitzaria osatzea:
- Eredua (`cnc_failure_model.pkl`) aplikazioaren abieran kargatu (`lifespan` erabiliz).
- Pydantic eskemak definitu sarrerako sentsore-datuentzat eta iragarpenarentzat.
- `/predict` endpoint-a inplementatu: datuak jaso, eredutik pasa, probabilitatea atera, eta alerta-maila esleitu.

**Dokumentazioa (Swagger):** `http://localhost:8000/docs`

**Eskaera (NiFi-k POST egingo dio):**
```json
POST http://scoring-api:8000/predict
{
  "timestamp":       "2026-04-29T10:57:50Z",
  "machine_id":      "CNC-039",
  "machine_type":    "L",
  "air_temp_K":      299.0,
  "process_temp_K":  308.6,
  "rpm":             1587,
  "torque_Nm":       38.6,
  "tool_wear_min":   124
}
```

**Erantzuna:**
```json
{
  "machine_id":          "CNC-039",
  "failure_predicted":   false,
  "failure_probability": 0.0341,
  "alert_level":         "OK"
}
```

Alert mailak: `OK` (< %50) · `KONTUZ` (%50–80) · `LARRIA` (> %80)

### Zure Zeregina NiFi-n (3. fasea)

NiFi flow berri bat sortu (edo lehena hedatu).

### Kibana Alerta-Dashboarda

Sortu dashboard berri bat:

- **Gauge:** hutsegite-probabilitate maximoa une honetan
- **Data table:** `LARRIA` mailako alertak azken orduan (makina_id, probabilitatea, ordua)
- **Line chart:** probabilitate-joera makina bakoitzeko
- **Color coding:** berdea < %50 · horia %50–80 · gorria > %80

### 💬 Pentsatzeko Galderak — 3. Fasea

**G9.** Scoring-api-k modeloa **abieran behin** kargatzen du, ez eskaera bakoitzean.
Zergatik da hau garrantzitsua? Zer gertatuko litzateke eskaera bakoitzean kargatuko balu?
(Pentsatu 1.000 makina badaude eta segundoko datuak bidaltzen ari badira.)

**G10.** Sistema honek alerta bat sortzen duenean, zer egin beharko luke enpresak
ondoren? Soilik Kibana alerta bat nahikoa da, ala beste zerbait behar da? Nola
automatizatu liteke erantzuna?

**G11.** Orain datuak bi indizetan gordetzen ditugu: `cnc-sensors` (1. fasea) eta
`cnc-predictions` (3. fasea). Zer abantaila du bi indize izateak bakarra izatearen
aldean? Eta zer desabantaila?

**G12.** Eredua orain dela 6 hilabete entrenatu zen. Fabrika berria egin du makina-mota
berri bat. Zer arazo ekar dezake honek eta nola konpon liteke? (Pentsatu: **model drift**
kontzeptua.)

---

## Entregablea Orokorra

### GitHub Repositorioa

```
cnc-guard/
├── README.md                    ← Proiektuaren azalpena eta abiarazteko argibideak
├── docker-compose.yml
├── nifi-flows/
│   ├── fase1_ingest.json        ← 1. faseko NiFi flow exportatua
│   └── fase3_streaming.json     ← 3. faseko NiFi flow exportatua
├── notebooks/
│   └── 02_training.ipynb        ← Osatuta eta dokumentatuta
├── models/
│   └── cnc_failure_model.pkl
└── dashboards/
    └── kibana_export.ndjson     ← Kibana dashboard exportatua
```

### Demo Aurkezpena (10 minutu)

1. Sistema live erakutsi — simuladorearen datuak Kibana-n agertzen dira (%2)
2. 2. faseko notebook-a eta emaitzak azaldu (%3)
3. Alerta bat simulatu — `LARRIA` maila Kibana-n erakutsi (%2)
4. Taldeak hartu dituen erabaki teknikoen justifikazioa (%3)

---

## Ebaluazio-Laburpena

| Fasea | Pisua |
|---|---|
| 1. fasea — Big Data pipeline | %35 |
| 2. fasea — ML entrenamendua | %40 |
| 3. fasea — Integrazioa | %25 |

**Puntuazio gehigarria (+5 puntu bakoitza):**
- Feature engineering originalak
- Eredu bat baino gehiago konparatu (RandomForest vs. beste bat)
- README dokumentazio bikaina
