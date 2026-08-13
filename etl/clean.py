"""Clean and normalize extracted KB documents."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Unicode-normalize, strip control chars, and collapse excess whitespace."""
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def clean_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the document with cleaned text."""
    cleaned = dict(doc)
    cleaned["text"] = normalize_text(str(doc.get("text", "")))
    if cleaned.get("practice_area"):
        cleaned["practice_area"] = normalize_text(str(cleaned["practice_area"]))
    return cleaned


def clean_all(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Clean a batch of documents and drop empties."""
    cleaned = [clean_document(doc) for doc in documents]
    return [doc for doc in cleaned if doc.get("text")]


if __name__ == "__main__":
    from extract import extract_all

    docs = clean_all(extract_all())
    print(f"Cleaned {len(docs)} documents")
    print(docs[0]["text"][:200] if docs else "No documents")
