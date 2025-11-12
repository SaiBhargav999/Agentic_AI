import os
import asyncio
import httpx
from typing import Any, Dict, Optional
from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv

from crew_logic import build_health_assessment_crew

load_dotenv(find_dotenv(), override=True)  # loads from project-root .env when run from VS Code / terminal

FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "https://hapi.fhir.org/baseR4")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = FastAPI(title="CrewAI FHIR Agent", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for demo; restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AssessmentIn(BaseModel):
    patient_id: str

def _require_key():
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is not set. Add it to your .env and restart the server."
        )

@app.get("/")
def root():
    return {"service": "crewai_fhir_agent", "status": "ok"}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/assessment/comprehensive")
async def comprehensive(in_body: AssessmentIn = Body(...)):
    """
    Fetch FHIR resources for the given patient and run a 2-step CrewAI assessment.
    """
    _require_key()

    # -------- 1) Fetch FHIR data (best-effort, small pages) --------
    patient_id = in_body.patient_id.strip()
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id is required")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            patient = (await client.get(f"{FHIR_BASE_URL}/Patient/{patient_id}")).json()

            # If patient doesn't exist, patient.get('resourceType') may be 'OperationOutcome'
            if patient.get("resourceType") == "OperationOutcome":
                raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found on FHIR server.")

            conditions = (await client.get(
                f"{FHIR_BASE_URL}/Condition",
                params={"patient": patient_id, "_count": 10}
            )).json()

            medications = (await client.get(
                f"{FHIR_BASE_URL}/MedicationRequest",
                params={"patient": patient_id, "_count": 10}
            )).json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"FHIR fetch error: {e!s}")

    # -------- 2) Run CrewAI workflow (blocking -> run in a thread) --------
    crew = build_health_assessment_crew()
    payload = {"patient": patient, "conditions": conditions, "medications": medications}

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None, lambda: crew.kickoff(inputs={"patient_json": payload})
        )
    except Exception as e:
        # Common causes: invalid/missing OPENAI_API_KEY or network to model provider
        raise HTTPException(status_code=500, detail=f"CrewAI error: {e!s}")

    # CrewAI can return a complex object; coerce to string for safety
    return {
        "patient_id": patient_id,
        "model": MODEL_NAME,
        "summary": str(result),
        "source_counts": {
            "conditions": len(conditions.get("entry", [])) if isinstance(conditions, dict) else None,
            "medicationRequests": len(medications.get("entry", [])) if isinstance(medications, dict) else None,
        },
    }
