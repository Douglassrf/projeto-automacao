from fastapi import FastAPI

app = FastAPI(title="Motor Emergencial")


@app.get("/")
def home():
    return {"status": "MOTOR_LIGADO", "agentes": "modo_emergencia"}


@app.get("/health")
def health():
    return {"ok": True}
