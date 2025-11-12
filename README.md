# 🩺 Agentic Healthcare AI

A local demo showing how **AI agents** analyze patient data using the open **FHIR** standard.  
Built with **FastAPI + React + CrewAI + Autogen**, powered by OpenAI models and public synthetic FHIR data.

---

## 🚀 Overview

| Layer | Tech | Purpose |
|:--|:--|:--|
| UI | React + TypeScript + MUI | Dashboard to enter Patient IDs and view AI outputs |
| Backend A | FastAPI + CrewAI | REST API: clinical summary + medication review |
| Backend B | FastAPI + Autogen | WebSocket stream: clinician ↔ pharmacist chat |
| Data | HAPI FHIR Public Server | Synthetic patients / conditions / medications |

Services run locally:  
**CrewAI → :8000 Autogen → :8001 UI → :3030**

---

## ⚙️ Setup

### Prerequisites
- Python 3.11+  
- Node 20+ and npm 10+  
- Git installed

Create a `.env` file in the project root:

OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o
FHIR_BASE_URL=https://hapi.fhir.org/baseR4

## CrewAI Backend

- cd crewai_fhir_agent
- pip install fastapi "uvicorn[standard]" httpx python-dotenv pydantic crewai openai
- uvicorn main:app --reload --port 8000
- http://127.0.0.1:8000/health
- POST /assessment/comprehensive
- Body: { "patient_id": "<FHIR ID>" }


## Autogen Backend

- cd autogen_fhir_agent
- pip install fastapi "uvicorn[standard]" websockets httpx python-dotenv
- pip install "autogen-agentchat" "autogen-ext[openai]"
- uvicorn main:app --reload --port 8001
- http://127.0.0.1:8001/health
- ws://127.0.0.1:8001/ws/conversation/<patient_id>

## React UI
- cd ui
- npm i
- npm run dev
