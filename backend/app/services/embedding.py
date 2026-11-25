"""Ollama embedding service with Redis caching (async + sync flavors)."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any

import httpx
import ollama

from app.core import cache
from app.core.config import Settings, get_settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger("embedding")

MAX_EMBED_BATCH_RETRIES = 2


class EmbeddingService:
    """Embeds text via Ollama ``/api/embed``; query embeddings are cached in Redis."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._async_client = ollama.AsyncClient(
            host=self._settings.ollama_base_url,
            timeout=httpx.Timeout(self._settings.ollama_timeout_seconds, connect=5.0),
        )
        self._sync_client = ollama.Client(
            host=self._settings.ollama_base_url,
            timeout=httpx.Timeout(self._settings.ollama_timeout_seconds, connect=5.0),
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @property
    def model(self) -> str:
        return self._settings.embedding_model

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        return text.strip()[:max_chars]

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(f"{self.model}:{text}".encode("utf-8")).hexdigest()
        return f"emb:{digest}"

    @staticmethod
    def _extract_vectors(response: Any) -> list[list[float]]:
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None and isinstance(response, dict):
            embeddings = response.get("embeddings")
        if not embeddings:
            raise ExternalServiceError("Ollama returned an empty embedding response.")
        return embeddings

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (Redis-cached)."""
        cleaned = self._truncate(text, self._settings.max_embed_chars) or " "
        key = self._cache_key(cleaned)

        cached = await cache.cache_get_json(key)
        if isinstance(cached, list) and cached:
            return cached

        try:
            response = await self._async_client.embed(model=self.model, input=[cleaned])
        except (ollama.ResponseError, httpx.HTTPError) as exc:
            logger.error("Embedding request failed: %s", exc)
            raise ExternalServiceError("Embedding model is unavailable.") from exc

        vectors = self._extract_vectors(response)
        vector = [float(x) for x in vectors[0]]
        await cache.cache_set_json(key, vector, self._settings.embedding_cache_ttl)
        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of chunk texts (sync — used by the Celery worker)."""
        settings = self._settings
        cleaned = [self._truncate(t, settings.max_embed_chars) or " " for t in texts]
        vectors: list[list[float]] = []
        for start in range(0, len(cleaned), settings.embed_batch_size):
            batch = cleaned[start : start + settings.embed_batch_size]
            try:
                response = self._sync_client.embed(model=self.model, input=batch)
            except (ollama.ResponseError, httpx.HTTPError) as exc:
                logger.error("Embedding batch failed: %s", exc)
                raise ExternalServiceError("Embedding model is unavailable.") from exc
            vectors.extend([float(x) for x in vec] for vec in self._extract_vectors(response))
        if len(vectors) != len(cleaned):
            raise ExternalServiceError("Embedding count mismatch from Ollama.")
        return vectors


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Process-wide singleton."""
    return EmbeddingService()
