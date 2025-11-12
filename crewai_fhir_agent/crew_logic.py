import os
from crewai import Agent, Task, Crew, Process

def build_health_assessment_crew() -> Crew:
    clinician = Agent(
        role="Clinician",
        goal="Create a concise, clinically sound patient summary in plain text.",
        backstory=(
            "You are a careful clinician. Use only the provided data. "
            "If something is missing, say 'unknown'. Never invent facts."
        ),
        verbose=True,
    )

    pharmacist = Agent(
        role="Pharmacist",
        goal="Identify medication risks, interactions, contraindications and data gaps in plain text.",
        backstory=(
            "You analyze medications for safety. If meds are missing or unclear, "
            "state that plainly and avoid speculation."
        ),
        verbose=True,
    )

    task_summary = Task(
        description=(
            "Write a concise clinical summary from the provided patient JSON. "
            "Output PLAIN TEXT only (no markdown, no bullets, no asterisks). "
            "Include demographics (if present), key conditions, and notable observations.\n\n{patient_json}"
        ),
        expected_output="3–6 sentences in plain text; no markdown formatting.",
        agent=clinician,
    )

    task_med_review = Task(
        description=(
            "From the same patient JSON, write a short medication safety review. "
            "Flag interactions/contraindications and call out unknowns. "
            "Output PLAIN TEXT only (no markdown, no bullets, no asterisks).\n\n{patient_json}"
        ),
        expected_output="2–5 sentences in plain text; no markdown formatting.",
        agent=pharmacist,
    )

    crew = Crew(
        agents=[clinician, pharmacist],
        tasks=[task_summary, task_med_review],
        process=Process.sequential,
        verbose=True,
    )
    return crew