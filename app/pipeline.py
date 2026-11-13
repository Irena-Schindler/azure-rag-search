"""retrieve -> relevance threshold -> generate -> verify citations -> answer or refuse."""
from __future__ import annotations
import pathlib
from dataclasses import dataclass, field
from .chunking import load_corpus
from .config import Settings
from .generator import REFUSAL, ExtractiveGenerator, Generator, cited
from .retriever import LocalRetriever, Retriever

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"


@dataclass
class Answer:
    text: str
    sources: list[str] = field(default_factory=list)
    refused: bool = False
    reason: str = ""


class RagPipeline:
    def __init__(self, retriever: Retriever, generator: Generator, top_k: int = 4) -> None:
        self.retriever, self.generator, self.top_k = retriever, generator, top_k

    def ask(self, question: str) -> Answer:
        hits = [h for h in self.retriever.search(question, self.top_k) if h.score >= self.retriever.threshold]
        if not hits:
            return Answer(REFUSAL, refused=True, reason="no source above relevance threshold")
        text = self.generator.generate(question, hits)
        refs = cited(text)
        if REFUSAL in text:
            return Answer(REFUSAL, refused=True, reason="model found no answer in sources")
        if not refs or not refs <= set(range(1, len(hits) + 1)):
            return Answer(REFUSAL, refused=True, reason=f"invalid citations {sorted(refs)}")
        return Answer(text, sources=[hits[i - 1].chunk.source for i in sorted(refs)])


def local_pipeline(settings: Settings | None = None) -> RagPipeline:
    s = settings or Settings()
    return RagPipeline(LocalRetriever(load_corpus(DOCS)), ExtractiveGenerator(), s.top_k)


def azure_pipeline(settings: Settings) -> RagPipeline:  # pragma: no cover - needs Azure
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI
    from .generator import AzureOpenAIGenerator
    from .retriever import AzureSearchRetriever
    credential = DefaultAzureCredential()
    client = AzureOpenAI(
        azure_endpoint=settings.openai_endpoint, api_version=settings.api_version,
        azure_ad_token_provider=get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default"))

    def embed(text: str) -> list[float]:
        return client.embeddings.create(model=settings.embedding_deployment, input=text).data[0].embedding

    return RagPipeline(AzureSearchRetriever(settings, embed, credential),
                       AzureOpenAIGenerator(client, settings.chat_deployment), settings.top_k)


def from_settings(settings: Settings | None = None) -> RagPipeline:
    s = settings or Settings()
    return azure_pipeline(s) if s.azure else local_pipeline(s)
