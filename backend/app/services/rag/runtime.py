"""Lazy application-scoped Qdrant and local embedding adapters."""

from __future__ import annotations

from threading import Lock
from typing import Any

from fastapi import Request
from qdrant_client import QdrantClient

from backend.app.core.config import Settings
from backend.app.services.rag.embeddings import EmbeddingProvider, OllamaEmbeddingProvider
from backend.app.services.rag.qdrant_store import QdrantEvidenceStore


class RagRuntimeUnavailable(RuntimeError):
    """Configured vector service could not be opened; no credential or text details are exposed."""


def initialize_rag_state(app: Any) -> None:
    """Set up lazy service slots without opening files or network connections at startup."""
    app.state.rag_lock = Lock()
    app.state.rag_initialized = False
    app.state.rag_store = None
    app.state.rag_embedding_provider = None
    app.state.managed_rag_store = None


def get_rag_services(
    request: Request,
) -> tuple[QdrantEvidenceStore | None, EmbeddingProvider | None]:
    """Return injected test services or lazily construct configured runtime adapters."""
    app = request.app
    store = getattr(app.state, "rag_store", None)
    embedder = getattr(app.state, "rag_embedding_provider", None)
    if store is not None or embedder is not None:
        return store, embedder
    if app.state.rag_initialized:
        return None, None

    with app.state.rag_lock:
        if app.state.rag_initialized:
            return app.state.rag_store, app.state.rag_embedding_provider
        settings: Settings = app.state.settings
        client: QdrantClient | None = None
        try:
            if settings.qdrant_url:
                api_key = (
                    settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
                )
                client = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=api_key,
                    timeout=settings.rag_embedding_timeout_seconds,
                )
            elif settings.vector_db_path:
                client = QdrantClient(path=str(settings.vector_db_path))

            if client is not None:
                store = QdrantEvidenceStore(client, settings.qdrant_collection)
                embedder = OllamaEmbeddingProvider(
                    settings.ollama_base_url,
                    settings.ollama_embed_model,
                    settings.rag_embedding_timeout_seconds,
                )
                app.state.rag_store = store
                app.state.rag_embedding_provider = embedder
                app.state.managed_rag_store = store
        except Exception as exc:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            raise RagRuntimeUnavailable("The configured retrieval service is unavailable") from exc
        app.state.rag_initialized = True
        return store, embedder


def close_rag_state(app: Any) -> None:
    """Close only the Qdrant client created and owned by the application factory."""
    store = getattr(app.state, "managed_rag_store", None)
    if store is not None:
        store.close()
        app.state.managed_rag_store = None
        app.state.rag_store = None
        app.state.rag_embedding_provider = None
        app.state.rag_initialized = False
