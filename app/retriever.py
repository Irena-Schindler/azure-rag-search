"""Retrieval behind one interface.

LocalRetriever: BM25 in memory. Tests, evals and local development, no cloud needed.
AzureSearchRetriever: Azure AI Search hybrid query (BM25 + vector) re-ranked by the semantic ranker.
"""
from __future__ import annotations
import math, re
from collections import Counter
from dataclasses import dataclass
from typing import Protocol
from .chunking import Chunk


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class Retriever(Protocol):
    threshold: float
    def search(self, query: str, k: int) -> list[Hit]: ...


_STOP = set("der die das und oder ein eine einen ich wir sie es ist sind wie viele viel was wann wo wer "
            "mit von zu im in am an auf für bei pro bis nach the a an of to is are how what when "
            "kann darf muss habe hat ich mein meine man".split())


_UMLAUT = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})


def tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-zäöüß0-9]+", text.lower()):
        if w in _STOP or len(w) < 3:
            continue
        w = w.translate(_UMLAUT)
        for suf in ("ungen", "enes", "ung", "ene", "en", "es", "er", "e", "n", "s"):  # light German stemming
            if w.endswith(suf) and len(w) - len(suf) >= 4:
                w = w[: -len(suf)]
                break
        out.append(w)
    return out


def features(text: str) -> list[str]:
    """Stems plus character 4-grams of long words, so German compounds match their parts
    ("Reisebelege" ~ "Belege", "Urlaubstage" ~ "Urlaub")."""
    out = []
    for w in tokens(text):
        out.append(w)
        if len(w) >= 7:
            out += [f"#{w[i:i + 4]}" for i in range(len(w) - 3)]
    return out


class LocalRetriever:
    threshold = 2.5

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.docs = [features(f"{c.section} {c.section} {c.content}") for c in chunks]
        self.avg = sum(map(len, self.docs)) / len(self.docs)
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.k1, self.b = k1, b

    def search(self, query: str, k: int) -> list[Hit]:
        q = features(query)
        stems = {t for t in q if not t.startswith("#")}
        hits = []
        for chunk, doc in zip(self.chunks, self.docs):
            if not stems & set(doc):  # n-grams alone are too fuzzy: require one whole-word match
                continue
            tf = Counter(doc)
            s = sum(self.idf.get(t, 0) * tf[t] * (self.k1 + 1) /
                    (tf[t] + self.k1 * (1 - self.b + self.b * len(doc) / self.avg)) for t in q)
            if s > 0:
                hits.append(Hit(chunk, s))
        return sorted(hits, key=lambda h: h.score, reverse=True)[:k]


class AzureSearchRetriever:  # pragma: no cover - needs Azure
    """Hybrid search with semantic re-ranking. Authenticates with Entra ID, no admin keys in the app."""

    def __init__(self, settings, embed, credential=None) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.search.documents import SearchClient
        self.client = SearchClient(settings.search_endpoint, settings.search_index,
                                   credential or DefaultAzureCredential())
        self.embed = embed
        self.threshold = settings.min_score

    def search(self, query: str, k: int) -> list[Hit]:
        from azure.search.documents.models import VectorizedQuery
        results = self.client.search(
            search_text=query,
            vector_queries=[VectorizedQuery(vector=self.embed(query), k_nearest_neighbors=k * 2,
                                            fields="contentVector")],
            query_type="semantic", semantic_configuration_name="default",
            select=["id", "title", "section", "content"], top=k)
        return [Hit(Chunk(r["id"], r["title"], r["section"], r["content"]),
                    r.get("@search.reranker_score") or r["@search.score"]) for r in results]
