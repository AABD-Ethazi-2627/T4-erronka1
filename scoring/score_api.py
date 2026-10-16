from fastapi import FastAPI

app = FastAPI(title="CNC Failure Scoring API")

@app.get("/")
def root():
    return {"message": "CNC Scoring API Activa"}
