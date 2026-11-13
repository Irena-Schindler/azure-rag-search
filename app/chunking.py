"""Split Markdown documents into one chunk per section (## heading). Sections are what people cite."""
from __future__ import annotations
import pathlib, re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    id: str
    title: str
    section: str
    content: str

    @property
    def source(self) -> str:
        return f"{self.title} › {self.section}"


def chunk_markdown(path: pathlib.Path) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    title = re.search(r"^# (.+)$", text, re.M).group(1).strip()
    parts = re.split(r"^## ", text, flags=re.M)[1:]
    chunks = []
    for part in parts:
        section, _, body = part.partition("\n")
        slug = re.sub(r"[^a-z0-9]+", "-", f"{path.stem}-{section}".lower()).strip("-")
        chunks.append(Chunk(id=slug, title=title, section=section.strip(), content=body.strip()))
    return chunks


def load_corpus(folder: pathlib.Path) -> list[Chunk]:
    return [c for p in sorted(folder.glob("*.md")) for c in chunk_markdown(p)]
