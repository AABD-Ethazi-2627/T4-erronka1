# CNC Guard — Hasteko Argibideak

## 1. Windows + Docker Desktop

Docker Desktop abiarazi Linux edukiontziekin. [SECURITY.md](SECURITY.md) irakurri
SOPS + age konfiguratzeko eta lehendik dagoen `.env` inportatzeko. SMB bolumenak
`//192.168.75.150/cnc-stream` erabiltzen du; ez da NFS muntatu behar Windowsen.

## 2. Zerbitzuak abiarazi

```powershell
# Lehenik SECURITY.md: SOPS + age konfiguratu eta sekretuak inportatu/sortu.
.\.venv\Scripts\python.exe scripts/security.py up
.\.venv\Scripts\python.exe scripts/security.py compose ps
```

| Zerbitzua | URLa | Erabiltzailea / Pasahitza |
|---|---|---|
| Kafka | kafka:9092 (Docker barnetik) | — |
| NiFi | https://localhost:8443 | NIFI_USERNAME / NIFI_PASSWORD (SOPS) |
| Kibana | https://localhost:5601 | cncviewer / KIBANA_PASSWORD (SOPS) |
| Elasticsearch | https://localhost:9200 | Autenticacion Basic; ver SECURITY.md |
| Scoring API | https://localhost:8000/docs | Bearer SCORING_API_TOKEN (SOPS) |

## 3. Proiektuko fitxategiak

```
cnc-guard/
├── filebeat/
│   └── filebeat.yml          ← 1. fasea: ZURE ZEREGINA (osatu — Kafka outputera bideratu)
├── scoring/
│   └── score_api.py          ← 3. fasea: ZURE ZEREGINA (osatu hutsuneak FastAPI-n)
├── nifi-flows/
│   └── cnc_fase1_INCOMPLETO.json  ← 1. fasea: NiFi-n inportatu eta osatu (ConsumeKafka jada konfiguratuta)
├── notebooks/
│   └── 02_training_TEMPLATE.ipynb ← 2. fasea: ZURE ZEREGINA (osatu)
├── models/                   ← 2. fasea: hemen gorde model.pkl
└── data/
    └── ai4i2020_train.csv    ← entrenamendurako datuak
```

## 4. Erronkaren dokumentua

`ENUNTZIATUA.md` irakurri — hiru faseetan zer egin azaltzen du.

## Seguridad

Kafka guarda ahora mensajes, offsets y metadatos en su volumen persistente.
Consulta [KAFKA_PERSISTENCIA.md](KAFKA_PERSISTENCIA.md) para la migracion,
verificacion y recuperacion de su copia cifrada.

Consulta [SECURITY.md](SECURITY.md) para configurar SOPS + age en Windows, importar
el `.env` existente al almacen cifrado y configurar las conexiones HTTPS y
credenciales en NiFi. Desde el servidor puedes usar `https://localhost`.
El grupo accede por `https://192.168.75.221` usando los mismos puertos de la tabla.
El firewall limita el acceso a `192.168.75.0/24`. Comparte `output/acceso-grupo.zip`
para que cada equipo instale la CA publica y consulte las URLs.
