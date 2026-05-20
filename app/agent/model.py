"""Model layer — single place that builds the LLM + embeddings.

v1 uses Gemini for everything (Model Choice.md: one provider, one key). To swap
the reflection pass to Ollama Cloud or a local model later, change only
get_reflection_model() — e.g. `from langchain_ollama import ChatOllama`.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.config.settings import (
    CHAT_MODEL, EMBEDDING_MODEL, GEMINI_API_KEY, REFLECTION_MODEL,
)


def get_chat_model(temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    """Workhorse model for the ReAct loop (supplier selection)."""
    return ChatGoogleGenerativeAI(
        model=CHAT_MODEL, google_api_key=GEMINI_API_KEY, temperature=temperature,
    )


def get_reflection_model() -> ChatGoogleGenerativeAI:
    """High-stakes reflection pass. Swap this one to Ollama for the 3-layer setup."""
    return ChatGoogleGenerativeAI(
        model=REFLECTION_MODEL, google_api_key=GEMINI_API_KEY, temperature=0.2,
    )


@lru_cache(maxsize=1)
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL, google_api_key=GEMINI_API_KEY,
    )
