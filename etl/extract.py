"""Extract raw knowledge-base documents from kb/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KB_DIR = Path(__file__).resolve().parent.parent / "kb"

JSON_SOURCES = [
    "practice_areas.json",
    "acceptance_criteria.json",
    "fee_structure.json",
    "sol_tables.json",
    "past_cases.json",
    "attorneys.json",
    "clients.json",
]

MARKDOWN_SOURCES = [
    "faqs.md",
]


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _flatten_practice_areas(data: list[str], source: str) -> list[dict[str, Any]]:
    return [
        {
            "source": source,
            "doc_type": "practice_area",
            "practice_area": name,
            "raw": name,
            "text": name,
        }
        for name in data
    ]


def _flatten_keyed_object(data: dict[str, Any], source: str, doc_type: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for practice_area, payload in data.items():
        docs.append(
            {
                "source": source,
                "doc_type": doc_type,
                "practice_area": practice_area,
                "raw": payload,
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        )
    return docs


def _flatten_keyed_list(data: dict[str, list[Any]], source: str, doc_type: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for practice_area, items in data.items():
        for index, item in enumerate(items):
            docs.append(
                {
                    "source": source,
                    "doc_type": doc_type,
                    "practice_area": practice_area,
                    "item_index": index,
                    "raw": item,
                    "text": json.dumps(item, ensure_ascii=False, indent=2),
                }
            )
    return docs


def _flatten_markdown(path: Path, source: str) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    return [
        {
            "source": source,
            "doc_type": "faq",
            "practice_area": None,
            "raw": text,
            "text": text,
        }
    ]


def extract_all(kb_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load and flatten all KB files into document records."""
    root = kb_dir or KB_DIR
    documents: list[dict[str, Any]] = []

    practice_areas_path = root / "practice_areas.json"
    if practice_areas_path.exists():
        documents.extend(
            _flatten_practice_areas(_read_json(practice_areas_path), practice_areas_path.name)
        )

    keyed_object_sources = {
        "acceptance_criteria.json": "acceptance_criteria",
        "fee_structure.json": "fee_structure",
        "sol_tables.json": "sol_rules",
    }
    for filename, doc_type in keyed_object_sources.items():
        path = root / filename
        if path.exists():
            documents.extend(_flatten_keyed_object(_read_json(path), filename, doc_type))

    keyed_list_sources = {
        "past_cases.json": "past_case",
        "attorneys.json": "attorney",
        "clients.json": "client",
    }
    for filename, doc_type in keyed_list_sources.items():
        path = root / filename
        if path.exists():
            documents.extend(_flatten_keyed_list(_read_json(path), filename, doc_type))

    for filename in MARKDOWN_SOURCES:
        path = root / filename
        if path.exists():
            documents.extend(_flatten_markdown(path, filename))

    return documents


if __name__ == "__main__":
    docs = extract_all()
    print(f"Extracted {len(docs)} documents from {KB_DIR}")
    for doc in docs[:5]:
        print(f"- {doc['source']} | {doc['doc_type']} | {doc.get('practice_area')}")
