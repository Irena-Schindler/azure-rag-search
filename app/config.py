"""Settings from environment variables. No secrets: Azure access uses Entra ID (managed identity)."""
from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    search_endpoint: str | None = os.getenv("AZURE_SEARCH_ENDPOINT")
    search_index: str = os.getenv("AZURE_SEARCH_INDEX", "handbook")
    openai_endpoint: str | None = os.getenv("AZURE_OPENAI_ENDPOINT")
    chat_deployment: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "chat")
    embedding_deployment: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "embedding")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    top_k: int = int(os.getenv("TOP_K", "4"))
    # minimum relevance: semantic reranker score (0..4) on Azure, normalised BM25 score locally
    min_score: float = float(os.getenv("MIN_SCORE", "1.5"))

    @property
    def azure(self) -> bool:
        return bool(self.search_endpoint and self.openai_endpoint)
