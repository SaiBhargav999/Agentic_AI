# autogen_fhir_agent/main.py
from fastapi import FastAPI

app = FastAPI(title="Autogen FHIR Agent (Skeleton)", version="0.1.0")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/hello")
def hello(name: str = "world"):
    return {"message": f"Hello, {name} from autogen_fhir_agent!"}
