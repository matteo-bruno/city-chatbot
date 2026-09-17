"""The chatbot's reference library.

Two tiers, deliberately:

* `knowledge/core/*.md` is small and goes into the system prompt on every
  request, behind a prompt-cache breakpoint. The model therefore "knows" the
  concept, the methodology and the reporting rules without a retrieval step.
* `knowledge/papers/*.md` is long-form source material. It is chunked and
  searched on demand with a BM25 ranking, so a methodological follow-up can be
  answered with the paper's own wording without paying for it every turn.

Adding a reference is a matter of dropping a markdown file into one of those
directories (use `scripts/ingest_pdf.py` for PDFs).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

WORD_RE = re.compile(r"[a-z0-9][a-z0-9'\-]*")

STOPWORDS = frozenset(
    """
    a about all also an and any are as at be been but by can do does for from
    had has have how i if in into is it its may more most no not of on or other
    our out over per so some such than that the their then there these they this
    those to under up use used using very was we were what when where which
    while who why will with within would you your
    """.split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in WORD_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


@dataclass
class Chunk:
    doc_id: str
    doc_title: str
    heading: str
    text: str
    tokens: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    def reference(self) -> str:
        return f"{self.doc_title} - {self.heading}" if self.heading else self.doc_title


def _hard_split(block: str, max_chars: int) -> list[str]:
    """Break an oversized block on line boundaries (PDF text has no blank lines)."""
    parts: list[str] = []
    current: list[str] = []
    size = 0
    for line in block.splitlines():
        if size + len(line) > max_chars and current:
            parts.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        parts.append("\n".join(current))
    return parts


def _split_markdown(text: str, max_chars: int = 1400) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) chunks, breaking long sections up."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        if line.startswith("#"):
            sections.append((line.lstrip("#").strip(), []))
        else:
            sections[-1][1].append(line)

    chunks: list[tuple[str, str]] = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        if len(body) <= max_chars:
            chunks.append((heading, body))
            continue
        current: list[str] = []
        size = 0
        blocks = [
            piece
            for para in re.split(r"\n\s*\n", body)
            for piece in (_hard_split(para, max_chars) if len(para) > max_chars else [para])
        ]
        for para in blocks:
            if size + len(para) > max_chars and current:
                chunks.append((heading, "\n\n".join(current)))
                current, size = [], 0
            current.append(para)
            size += len(para) + 2
        if current:
            chunks.append((heading, "\n\n".join(current)))
    return chunks


class KnowledgeBase:
    """Always-on core documents plus a searchable long-form corpus."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.core: list[tuple[str, str]] = []  # (title, text)
        self.chunks: list[Chunk] = []
        self._df: dict[str, int] = {}
        self._avg_len = 1.0
        self._load()

    # ---------------------------------------------------------------- loading

    def _load(self) -> None:
        for path in sorted((self.root / "core").glob("*.md")):
            self.core.append((self._title_of(path), path.read_text(encoding="utf-8").strip()))
        for path in sorted((self.root / "papers").glob("*.md")):
            self._index_document(path)
        self._finalise_index()

    @staticmethod
    def _title_of(path: Path) -> str:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return path.stem.replace("-", " ")

    def _index_document(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        title = self._title_of(path)
        for heading, body in _split_markdown(text):
            tokens = tokenize(f"{heading} {body}")
            if not tokens:
                continue
            counts: dict[str, int] = {}
            for tok in tokens:
                counts[tok] = counts.get(tok, 0) + 1
            self.chunks.append(
                Chunk(
                    doc_id=path.stem,
                    doc_title=title,
                    heading=heading,
                    text=body,
                    tokens=tokens,
                    counts=counts,
                )
            )

    def _finalise_index(self) -> None:
        for chunk in self.chunks:
            for tok in chunk.counts:
                self._df[tok] = self._df.get(tok, 0) + 1
        if self.chunks:
            self._avg_len = sum(len(c.tokens) for c in self.chunks) / len(self.chunks)

    # ------------------------------------------------------------- core block

    def core_text(self) -> str:
        return "\n\n".join(text for _, text in self.core)

    # ---------------------------------------------------------------- search

    def search(self, query: str, limit: int = 4) -> list[dict]:
        """BM25 ranking over the long-form corpus."""
        terms = tokenize(query)
        if not terms or not self.chunks:
            return []
        n = len(self.chunks)
        k1, b = 1.5, 0.75
        scored: list[tuple[float, Chunk]] = []
        for chunk in self.chunks:
            score = 0.0
            length = len(chunk.tokens)
            for term in terms:
                tf = chunk.counts.get(term, 0)
                if not tf:
                    continue
                df = self._df.get(term, 0)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * length / self._avg_len))
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda p: (-p[0], p[1].doc_id, p[1].heading))
        return [
            {
                "source": chunk.reference(),
                "document": chunk.doc_id,
                "relevance": round(score, 3),
                "text": chunk.text,
            }
            for score, chunk in scored[:limit]
        ]

    def documents(self) -> list[dict]:
        seen: dict[str, dict] = {}
        for chunk in self.chunks:
            entry = seen.setdefault(
                chunk.doc_id, {"document": chunk.doc_id, "title": chunk.doc_title, "sections": 0}
            )
            entry["sections"] += 1
        return sorted(seen.values(), key=lambda d: d["document"])
