"""HTTP API. Runs locally without Azure; on Azure Container Apps it uses the managed identity."""
from __future__ import annotations
from functools import lru_cache
from fastapi import FastAPI
from pydantic import BaseModel, Field
from .config import Settings
from .pipeline import from_settings

app = FastAPI(title="azure-rag-search")


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@lru_cache
def pipeline():
    return from_settings(Settings())


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "mode": "azure" if Settings().azure else "local"}


@app.post("/ask")
def ask(q: Question) -> dict:
    a = pipeline().ask(q.question)
    return {"answer": a.text, "sources": a.sources, "refused": a.refused}
