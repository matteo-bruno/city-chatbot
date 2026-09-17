#!/usr/bin/env python3
"""Convert a reference PDF into a markdown document the chatbot can search.

    python scripts/ingest_pdf.py paper.pdf --out knowledge/papers/my-paper.md \
        --title "A universal framework for inclusive 15-minute cities" \
        --citation "Bruno, M. et al. Nature Cities 1, 633-641 (2024)"

Markdown is the storage format on purpose: the retrieval tool searches plain
text, and a human can read and correct the result. Needs `pip install pypdf`.
Scanned PDFs yield no text - run OCR first.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADER_NOISE = re.compile(
    r"^(nature cities|article\s+https?://\S+|https?://doi\.org/\S+)\s*$", re.IGNORECASE
)


def clean_page(text: str) -> str:
    """Drop running heads and rejoin words hyphenated across a line break."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    lines = [ln for ln in lines if not HEADER_NOISE.match(ln.strip())]
    text = "\n".join(lines)
    text = re.sub(r"(\w)-\s*\n(\w)", r"\1\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("source", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--citation", default=None)
    ap.add_argument("--url", default=None)
    args = ap.parse_args()

    try:
        from pypdf import PdfReader
    except ImportError:
        print("error: pip install pypdf  (see requirements-prep.txt)", file=sys.stderr)
        return 1

    reader = PdfReader(str(args.source))
    parts: list[str] = []
    title = args.title or args.source.stem.replace("_", " ")
    parts.append(f"# {title}\n")
    if args.citation:
        parts.append(f"**Citation:** {args.citation}\n")
    if args.url:
        parts.append(f"**Source:** {args.url}\n")
    parts.append(f"*Extracted from {args.source.name}, {len(reader.pages)} pages.*\n")

    empty = 0
    for i, page in enumerate(reader.pages, start=1):
        body = clean_page(page.extract_text() or "")
        if not body:
            empty += 1
            continue
        parts.append(f"\n## Page {i}\n\n{body}\n")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(parts), encoding="utf-8")
    words = len(args.out.read_text(encoding="utf-8").split())
    print(f"wrote {args.out} ({words} words, {empty} page(s) with no extractable text)")
    if empty == len(reader.pages):
        print("warning: no text extracted at all - is this a scanned PDF?", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
