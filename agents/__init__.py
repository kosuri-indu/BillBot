"""Agents package exports for BillBot.

This module exposes the existing agent modules so `from agents import ...` works
even when the underlying implementations are added here.
"""
"""Lightweight agents package initializer.

Only import the chat agent by default to avoid importing optional/LangChain
backed agents at package import time. This keeps `from agents import ...`
safe when LangChain or other optional deps are not installed.
"""
from . import chat_agent

__all__ = ["chat_agent"]
