import os
import re
import asyncio
import httpx
from typing import Any, Dict
from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv

from crew_logic import build_health_assessment_crew

# Load env from project root
load_dotenv(find_dotenv(), override=True)

FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "https://hapi.fhir.org/baseR4")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = FastAPI(title="CrewAI FHIR Agent", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for prod
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

def _to_plain(text: str) -> str:
    """Strip common markdown to plain text."""
    if not isinstance(text, str):
        text = str(text)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)  # **bold**/*italic*
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", text)     # `code`
    text = re.sub(r"^[\s>*-]+\s*", "", text, flags=re.MULTILINE)  # bullets/quotes
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

@app.get("/")
def root():
    return {"service": "crewai_fhir_agent", "status": "ok"}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/assessment/comprehensive")
async def comprehensive(in_body: AssessmentIn = Body(...)):
    """Fetch FHIR resources for the given patient and run a 2-step CrewAI assessment."""
    _require_key()

    patient_id = in_body.patient_id.strip()
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id is required")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            patient = (await client.get(f"{FHIR_BASE_URL}/Patient/{patient_id}")).json()
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

    crew = build_health_assessment_crew()
    payload = {"patient": patient, "conditions": conditions, "medications": medications}

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None, lambda: crew.kickoff(inputs={"patient_json": payload})
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CrewAI error: {e!s}")

    plain = _to_plain(str(result))
    return {
        "patient_id": patient_id,
        "model": MODEL_NAME,
        "summary": plain,
        "source_counts": {
            "conditions": len(conditions.get("entry", [])) if isinstance(conditions, dict) else None,
            "medicationRequests": len(medications.get("entry", [])) if isinstance(medications, dict) else None,
        },
    }