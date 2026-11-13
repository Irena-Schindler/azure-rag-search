"""Retrieval and refusal eval.

    python -m evals.run       # local BM25, enforced in CI (semantic cases reported, not enforced)
    (with AZURE_* set)        # Azure hybrid + semantic ranker, all cases enforced
"""
from __future__ import annotations
import pathlib, sys
import yaml
from app.config import Settings
from app.pipeline import from_settings

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    settings = Settings()
    pipe = from_settings(settings)
    cases = yaml.safe_load((ROOT / "evals/questions.yaml").read_text(encoding="utf-8"))
    hit = rr = refuse_ok = n_ans = n_ref = 0
    sem_hit = n_sem = 0
    failures = []
    for c in cases:
        hits = [h for h in pipe.retriever.search(c["q"], 3) if h.score >= pipe.retriever.threshold]
        sections = [h.chunk.section for h in hits]
        answer = pipe.ask(c["q"])
        if c["expect"] is None:
            n_ref += 1
            refuse_ok += answer.refused
            if not answer.refused:
                failures.append(f"should refuse: {c['q']}")
            continue
        found = c["expect"] in sections and not answer.refused
        if c.get("semantic") and not settings.azure:
            n_sem += 1
            sem_hit += found
            continue
        n_ans += 1
        hit += found
        rr += 1 / (sections.index(c["expect"]) + 1) if c["expect"] in sections else 0
        if not found:
            failures.append(f"missed {c['expect']}: {c['q']} -> {sections}")
    print(f"mode: {'azure' if settings.azure else 'local BM25'}")
    print(f"hit@3 {hit}/{n_ans} | MRR {rr / n_ans:.2f} | correct refusals {refuse_ok}/{n_ref}")
    if n_sem:
        print(f"paraphrases without shared words (need vector search): {sem_hit}/{n_sem} found locally")
    for f in failures:
        print("  ", f)
    return 0 if hit == n_ans and refuse_ok == n_ref else 1


if __name__ == "__main__":
    sys.exit(main())
