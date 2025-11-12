import os
import json
import httpx
from dotenv import load_dotenv, find_dotenv
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(find_dotenv(), override=True)  # find .env in repo root

from agents import build_agents

FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "https://hapi.fhir.org/baseR4")

app = FastAPI(title="Autogen FHIR Agent", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # demo; tighten for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        # 1) Pull minimal FHIR snapshot (best effort)
        async with httpx.AsyncClient(timeout=30.0) as client:
            patient = (await client.get(f"{FHIR_BASE_URL}/Patient/{patient_id}")).json()
            conditions = (await client.get(
                f"{FHIR_BASE_URL}/Condition", params={"patient": patient_id, "_count": 10}
            )).json()
            meds = (await client.get(
                f"{FHIR_BASE_URL}/MedicationRequest", params={"patient": patient_id, "_count": 10}
            )).json()

        # bail out early if not a real patient
        if isinstance(patient, dict) and patient.get("resourceType") == "OperationOutcome":
            await ws.send_text(f"[error] Patient '{patient_id}' not found on FHIR server.\n")
            await ws.close()
            return

        clinician, pharmacist, model_client = build_agents()

        # 2) Send a header line
        await ws.send_text(f"[connected] patient_id={patient_id}\n")

        # 3) Prepare concise context (cap size to avoid huge payloads)
        context = {"patient": patient, "conditions": conditions, "medications": meds}
        context_json = json.dumps(context)

        # 4) First agent: clinician summary (stream tokens)
        starter = (
            "Create a brief clinical summary using only this JSON. "
            "Call out unknowns explicitly.\n\n"
        ) + context_json + "\n"

        async for token in clinician.run_stream(task=starter):
            text = getattr(token, "delta", None) or getattr(token, "content", None)
            if text:
                await ws.send_text(text)

        await ws.send_text("\n---\n")

        # 5) Second agent: pharmacist review (stream tokens) — include JSON again
        followup = (
            "Now review medications for risks/interactions based on this SAME JSON. "
            "If medications are unknown/empty, say so clearly and stop.\n\n"
        ) + context_json + "\n"

        async for token in pharmacist.run_stream(task=followup):
            text = getattr(token, "delta", None) or getattr(token, "content", None)
            if text:
                await ws.send_text(text)

        await ws.send_text("\n---\nDone.\n")
        await ws.close()

    except WebSocketDisconnect:
        # client closed connection
        pass
    except Exception as e:
        try:
            await ws.send_text(f"\n[server-error] {e!s}\n")
            await ws.close()
        except Exception:
            pass
