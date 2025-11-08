"""Thin wrapper that exposes a clear narration agent API.

This delegates to `langchain_agents.generate_narration_agentic` so callers can
import `agents.narration_agent.generate_narration` for clarity.
"""
from typing import Dict, Any
from .langchain_agents import generate_narration_agentic


def generate_narration(user_id: str, months: int = 12) -> Dict[str, Any]:
    return generate_narration_agentic(user_id, months=months)
