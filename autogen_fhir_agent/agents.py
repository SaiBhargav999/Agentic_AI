import os
from typing import Tuple
from dotenv import load_dotenv, find_dotenv

# Ensure we can read the root .env regardless of CWD
load_dotenv(find_dotenv(), override=True)

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

def build_agents() -> Tuple[AssistantAgent, AssistantAgent, OpenAIChatCompletionClient]:
    model_name = os.getenv("MODEL_NAME", "gpt-4o")
    # OpenAI API key is read from OPENAI_API_KEY env var by the client
    client = OpenAIChatCompletionClient(model=model_name)

    clinician = AssistantAgent(
        name="clinician",
        model_client=client,
        system_message=(
            "You are a careful clinician. Use only the provided JSON. "
            "If information is missing, clearly say 'unknown'. Be concise."
        ),
        reflect_on_tool_use=True,
        model_client_stream=True,   # stream tokens
    )

    pharmacist = AssistantAgent(
        name="pharmacist",
        model_client=client,
        system_message=(
            "You are a pharmacist focused on medication safety and interactions. "
            "If medications are absent or unclear, state that plainly. Be concise."
        ),
        reflect_on_tool_use=True,
        model_client_stream=True,   # stream tokens
    )

    return clinician, pharmacist, client
