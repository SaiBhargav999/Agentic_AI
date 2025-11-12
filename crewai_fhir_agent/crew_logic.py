import os
from typing import Dict, Any
from crewai import Agent, Task, Crew, Process

# Crew definition:
def build_health_assessment_crew() -> Crew:
    clinician = Agent(
        role="Clinician",
        goal="Create a concise, clinically sound patient summary.",
        backstory=(
            "You are a careful clinician. Use only the provided JSON. "
            "If something is missing, say 'unknown'. Never invent facts."
        ),
        verbose=True,
    )

    pharmacist = Agent(
        role="Pharmacist",
        goal="Identify medication risks, interactions, and data gaps.",
        backstory=(
            "You analyze medications for safety. If meds are missing or unclear, "
            "state that plainly and avoid speculation."
        ),
        verbose=True,
    )

    task_summary = Task(
        description=(
            "Write a concise clinical summary from the provided patient JSON. "
            "Include demographics (if present), key conditions, and recent observations. "
            "Avoid speculation.\n\n{patient_json}"
        ),
        expected_output="A short bullet summary with *verified* facts only.",
        agent=clinician,
    )

    task_med_review = Task(
        description=(
            "From the same patient JSON, list current medications (if any) and flag "
            "potential interactions or contraindications. If unknown, say 'not available'.\n\n{patient_json}"
        ),
        expected_output="Bulleted medication review; call out risks and unknowns.",
        agent=pharmacist,
    )

    crew = Crew(
        agents=[clinician, pharmacist],
        tasks=[task_summary, task_med_review],
        process=Process.sequential,  # Clinician first, then Pharmacist
        verbose=True,
    )
    return crew
