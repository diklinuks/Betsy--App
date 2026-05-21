"""Model layer — single place that builds the LLM + embeddings.

v1 uses Gemini for everything (Model Choice.md: one provider, one key). To swap
the reflection pass to Ollama Cloud or a local model later, change only
get_reflection_model() — e.g. `from langchain_ollama import ChatOllama`.

A shared in-memory rate limiter throttles all chat calls so a full run stays under
the Gemini free-tier limit (~15 req/min) instead of crashing with 429s.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.config.settings import (
    CHAT_MODEL, EMBEDDING_MODEL, GEMINI_API_KEY, LLM_MAX_RETRIES, LLM_RPS,
    REFLECTION_MODEL,
)

# One shared limiter across all chat calls (decision + reflection).
_rate_limiter = InMemoryRateLimiter(
    requests_per_second=LLM_RPS, check_every_n_seconds=0.5, max_bucket_size=2,
)


def get_chat_model(temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    """Workhorse model for the reorder decision."""
    return ChatGoogleGenerativeAI(
        model=CHAT_MODEL, google_api_key=GEMINI_API_KEY, temperature=temperature,
        rate_limiter=_rate_limiter, max_retries=LLM_MAX_RETRIES,
    )


def get_reflection_model() -> ChatGoogleGenerativeAI:
    """High-stakes reflection pass. Swap this one to Ollama for the 3-layer setup."""
    return ChatGoogleGenerativeAI(
        model=REFLECTION_MODEL, google_api_key=GEMINI_API_KEY, temperature=0.2,
        rate_limiter=_rate_limiter, max_retries=LLM_MAX_RETRIES,
    )


@lru_cache(maxsize=1)
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL, google_api_key=GEMINI_API_KEY,
    )
