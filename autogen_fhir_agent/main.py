import os
import json
import httpx
from typing import Any, Dict, List
from dotenv import load_dotenv, find_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(find_dotenv(), override=True)

from agents import build_agents

FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "https://hapi.fhir.org/baseR4")

app = FastAPI(title="Autogen FHIR Agent", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _sanitize_fhir(obj):
    """Remove noisy FHIR narrative/metadata fields to reduce token usage."""
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            if k in ("text", "meta", "contained", "extension"):
                continue
            cleaned[k] = _sanitize_fhir(v)
        return cleaned
    if isinstance(obj, list):
        return [_sanitize_fhir(v) for v in obj]
    return obj

def _extract_summary(patient: Dict[str, Any], conditions: Dict[str, Any], meds: Dict[str, Any]) -> str:
    pid = patient.get("id")
    gender = patient.get("gender", "unknown")
    birth = patient.get("birthDate", "unknown")

    conds: List[str] = []
    for e in conditions.get("entry", [])[:10]:
        r = e.get("resource", {})
        code = r.get("code", {})
        txt = code.get("text") or (code.get("coding", [{}])[0].get("display"))
        if txt:
            conds.append(txt)

    mr: List[str] = []
    for e in meds.get("entry", [])[:10]:
        r = e.get("resource", {})
        med = r.get("medicationCodeableConcept", {})
        txt = med.get("text") or (med.get("coding", [{}])[0].get("display"))
        if txt:
            mr.append(txt)

    return (
        f"Patient ID: {pid}\n"
        f"Gender: {gender}  BirthDate: {birth}\n"
        f"Conditions ({len(conds)}): {', '.join(conds) or 'none'}\n"
        f"Medications ({len(mr)}): {', '.join(mr) or 'none'}\n"
    )

@app.get("/")
def root():
    return {"service": "autogen_fhir_agent", "status": "ok"}

@app.get("/health")
def health():
    return {"ok": True}

@app.websocket("/ws/conversation/{patient_id}")
async def ws_conversation(ws: WebSocket, patient_id: str):
    await ws.accept()
    try:
        # 1) Fetch FHIR snapshot
        async with httpx.AsyncClient(timeout=30.0) as client:
            patient = (await client.get(f"{FHIR_BASE_URL}/Patient/{patient_id}")).json()
            conditions = (await client.get(
                f"{FHIR_BASE_URL}/Condition", params={"patient": patient_id, "_count": 10}
            )).json()
            meds = (await client.get(
                f"{FHIR_BASE_URL}/MedicationRequest", params={"patient": patient_id, "_count": 10}
            )).json()

        if patient.get("resourceType") == "OperationOutcome":
            await ws.send_text(f"[error] Patient '{patient_id}' not found on FHIR server.\n")
            await ws.close()
            return

        clinician, pharmacist, _ = build_agents()

        # 2) Compact “facts” text (no raw JSON)
        patient_s   = _sanitize_fhir(patient)
        conditions_s= _sanitize_fhir(conditions)
        meds_s      = _sanitize_fhir(meds)
        facts = _extract_summary(patient_s, conditions_s, meds_s)

        await ws.send_text(f"[connected] patient_id={patient_id}\n")

        # 3) Clinician turn (plain text only)
        starter = (
            "Create a brief clinical summary from the following FACTS. "
            "Output PLAIN TEXT only (no markdown, no bullets, no code blocks). "
            "If something is unknown, say 'unknown'.\n\n"
            f"{facts}\n"
        )
        async for token in clinician.run_stream(task=starter):
            text = getattr(token, "delta", None) or getattr(token, "content", None)
            if text:
                await ws.send_text(text)

        await ws.send_text("\n---\n")

        # 4) Pharmacist turn (plain text only)
        followup = (
            "Based on the same FACTS above, write a short medication safety review. "
            "Flag interactions/contraindications if any; otherwise say none. "
            "Output PLAIN TEXT only (no markdown, no bullets, no code blocks)."
        )
        async for token in pharmacist.run_stream(task=followup):
            text = getattr(token, "delta", None) or getattr(token, "content", None)
            if text:
                await ws.send_text(text)

        await ws.send_text("\n---\nDone.\n")
        await ws.close()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_text(f"\n[server-error] {e!s}\n")
            await ws.close()
        except Exception:
            pass
