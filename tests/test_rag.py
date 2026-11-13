import pathlib
from fastapi.testclient import TestClient
from app.chunking import load_corpus
from app.generator import REFUSAL
from app.indexer import index_definition
from app.main import app
from app.pipeline import DOCS, RagPipeline, local_pipeline
from app.retriever import LocalRetriever


def test_chunks_are_sections_with_stable_ids():
    chunks = load_corpus(DOCS)
    assert {"Urlaub", "Geräteverlust"} <= {c.section for c in chunks}
    assert len({c.id for c in chunks}) == len(chunks)


def test_answer_cites_its_source():
    a = local_pipeline().ask("Wie viele Urlaubstage habe ich?")
    assert not a.refused and "30 Urlaubstage" in a.text and "[1]" in a.text
    assert a.sources == ["Mitarbeiterhandbuch Nordwind Logistik › Urlaub"]


def test_refuses_when_nothing_relevant():
    a = local_pipeline().ask("Gibt es einen Firmenwagen?")
    assert a.refused and a.text == REFUSAL


class _Gen:
    def __init__(self, text):
        self.text = text

    def generate(self, question, hits):
        return self.text


def _pipe(text):
    return RagPipeline(LocalRetriever(load_corpus(DOCS)), _Gen(text))


def test_rejects_citation_of_a_source_that_was_not_retrieved():
    a = _pipe("Sie haben 45 Urlaubstage [7].").ask("Wie viele Urlaubstage habe ich?")
    assert a.refused and "invalid citations" in a.reason


def test_rejects_uncited_answer():
    assert _pipe("Sie haben 45 Urlaubstage.").ask("Wie viele Urlaubstage habe ich?").refused


def test_model_refusal_is_passed_through():
    a = _pipe(REFUSAL).ask("Wie viele Urlaubstage habe ich?")
    assert a.refused and a.reason == "model found no answer in sources"


def test_api_local_mode():
    client = TestClient(app)
    assert client.get("/healthz").json() == {"ok": True, "mode": "local"}
    r = client.post("/ask", json={"question": "Wie hoch ist die Homeoffice-Pauschale?"}).json()
    assert "20 Euro" in r["answer"] and r["sources"] and not r["refused"]
    assert client.post("/ask", json={"question": "x"}).status_code == 422


def test_index_definition_is_hybrid_and_semantic():
    idx = index_definition("handbook", 1536)
    vec = next(f for f in idx.fields if f.name == "contentVector")
    assert vec.vector_search_dimensions == 1536
    assert idx.semantic_search.configurations[0].name == "default"
    assert any(f.analyzer_name == "de.microsoft" for f in idx.fields if f.name == "content")
