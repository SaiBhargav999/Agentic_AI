from fastapi import FastAPI

app = FastAPI(title="CrewAI FHIR Agent (Skeleton)", version="0.1.0")

@app.get("/")
def root():
    return {"service": "crewai_fhir_agent", "status": "ok"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/hello")
def hello(name: str = "world"):
    return {"message": f"Hello, {name} from crewai_fhir_agent!"}
