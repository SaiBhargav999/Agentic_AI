import os
from typing import Tuple
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

def build_agents() -> Tuple[AssistantAgent, AssistantAgent, OpenAIChatCompletionClient]:
    model_name = os.getenv("MODEL_NAME", "gpt-4o")
    client = OpenAIChatCompletionClient(model=model_name)

    clinician = AssistantAgent(
        name="clinician",
        model_client=client,
        system_message=(
            "You are a careful clinician. Use only provided facts. "
            "If information is missing, say 'unknown'. Output plain text."
        ),
        reflect_on_tool_use=True,
        model_client_stream=True,
    )

    pharmacist = AssistantAgent(
        name="pharmacist",
        model_client=client,
        system_message=(
            "You are a pharmacist focused on medication safety. "
            "Flag interactions/contraindications and unknowns. Output plain text."
        ),
        reflect_on_tool_use=True,
        model_client_stream=True,
    )

    return clinician, pharmacist, client
