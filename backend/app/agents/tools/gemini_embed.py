"""Small Gemini embedding client used for KG ingestion and retrieval.

Safe to import without credentials or the Google SDK. Runtime calls raise
:class:`GeminiUnavailable` when Gemini cannot be used, so callers can fall back
to lexical/static retrieval in tests/dev.
"""

from __future__ import annotations

import asyncio
import os

from app.agents.tools.gemini_text import GeminiUnavailable, _api_key

EMBED_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
EMBED_DIM = 768


def _extract_vectors(response: object) -> list[list[float]]:
    """Pull plain float lists out of the SDK response shape."""

    embeddings = getattr(response, "embeddings", None)
    if embeddings is None:
        # Older SDKs used ``embedding`` (singular) for single-input calls.
        single = getattr(response, "embedding", None)
        embeddings = [single] if single is not None else None
    if not embeddings:
        raise GeminiUnavailable("Gemini embedding response did not include embeddings")

    vectors: list[list[float]] = []
    for item in embeddings:
        values = getattr(item, "values", None)
        if values is None and isinstance(item, (list, tuple)):
            values = list(item)
        if values is None:
            raise GeminiUnavailable("Gemini embedding item did not include values")
        vectors.append([float(v) for v in values])
    return vectors


def _embed_sync(texts: list[str], *, model: str) -> list[list[float]]:
    try:
        from google import genai
        from google.genai import types
    except Exception as exc:  # pragma: no cover - optional environment
        raise GeminiUnavailable("Gemini SDK is not installed or could not be imported") from exc

    try:
        client = genai.Client(api_key=_api_key())
        config = None
        try:
            config = types.EmbedContentConfig(output_dimensionality=EMBED_DIM)
        except (TypeError, AttributeError):  # older SDKs: no config kwarg
            config = None
        response = client.models.embed_content(model=model, contents=texts, config=config)
    except GeminiUnavailable:
        raise
    except Exception as exc:  # no secrets in message
        raise GeminiUnavailable(f"Gemini embedding failed: {exc.__class__.__name__}") from exc

    vectors = _extract_vectors(response)
    for vector in vectors:
        if len(vector) != EMBED_DIM:
            raise GeminiUnavailable(
                f"Gemini embedding dimension mismatch: expected {EMBED_DIM}, got {len(vector)}"
            )
    return vectors


async def embed(texts: list[str], *, model: str = EMBED_MODEL) -> list[list[float]]:
    """Return one 768-dim vector per input text. Raises GeminiUnavailable on failure."""

    if not texts:
        return []
    return await asyncio.to_thread(_embed_sync, texts, model=model)


def embed_sync(texts: list[str], *, model: str = EMBED_MODEL) -> list[list[float]]:
    """Synchronous variant for scripts (e.g. KG seeding)."""

    if not texts:
        return []
    return _embed_sync(texts, model=model)
