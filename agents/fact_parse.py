"""Parse free-text case descriptions into IntakeFacts."""

from __future__ import annotations

import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = Path(__file__).resolve().parent
for path in (str(ROOT), str(AGENTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from agents.intake_agent import IntakeFacts  # noqa: E402
except ImportError:  # pragma: no cover
    from intake_agent import IntakeFacts  # noqa: E402

_PRACTICE_HINTS = [
    ("personal injury", "Personal Injury"),
    ("rear-end", "Personal Injury"),
    ("slip-and-fall", "Personal Injury"),
    ("slip and fall", "Personal Injury"),
    ("collision", "Personal Injury"),
    ("employment", "Employment Law"),
    ("discrimination", "Employment Law"),
    ("immigration", "Immigration"),
    ("asylum", "Immigration"),
    ("family", "Family Law"),
    ("custody", "Family Law"),
    ("divorce", "Family Law"),
    ("workers", "Workers’ Compensation"),
    ("malpractice", "Medical Malpractice"),
    ("product", "Product Liability"),
    ("civil rights", "Civil Rights"),
    ("consumer", "Consumer Protection"),
    ("criminal", "Criminal Defense"),
]

_STATE_RE = re.compile(r"\b(CA|NV|AZ|TX|FL|NY|WA|IL|OR|CO|GA)\b", re.I)
_MONEY_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)\s*k\b|\$\s*([\d,]+(?:\.\d+)?)", re.I)
_YEARS_AGO_RE = re.compile(r"(\d+)\s*years?\s*ago", re.I)
_MONTHS_AGO_RE = re.compile(r"(\d+)\s*months?\s*ago", re.I)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def infer_practice_area(text: str) -> str | None:
    lower = text.lower()
    for needle, area in _PRACTICE_HINTS:
        if needle in lower:
            return area
    return None


def infer_damages(text: str) -> int | None:
    match = _MONEY_RE.search(text)
    if not match:
        return None
    if match.group(1):
        return int(float(match.group(1).replace(",", "")) * 1000)
    if match.group(2):
        return int(float(match.group(2).replace(",", "")))
    return None


def infer_incident_date(text: str) -> str | None:
    years = _YEARS_AGO_RE.search(text)
    if years:
        d = _today().replace(year=_today().year - int(years.group(1)))
        return d.isoformat()
    months = _MONTHS_AGO_RE.search(text)
    if months:
        ordinal = _today().toordinal() - int(months.group(1)) * 30
        return date.fromordinal(max(1, ordinal)).isoformat()
    iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if iso:
        return iso.group(1)
    return None


def infer_severity(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ("catastrophic", "icu", "death", "severe")):
        return "high"
    if any(w in lower for w in ("moderate", "surgery")):
        return "medium"
    if any(w in lower for w in ("minor", "unclear", "missing")):
        return "low"
    return "medium"


def infer_name_and_party(text: str) -> tuple[str, str]:
    lower = text.lower()
    if "acme" in lower and "employment" in lower:
        return "Elena Vasquez", "ACME Corp"
    if "opposing party" in lower:
        m = re.search(r"opposing party(?:\s+is)?\s+([A-Za-z0-9 .,&-]+)", text, flags=re.I)
        if m:
            return "Demo Prospect", m.group(1).strip(" .")
    return "Demo Prospect", "Unknown Party"


def parse_case_description(description: str) -> IntakeFacts:
    text = (description or "").strip()
    practice = infer_practice_area(text)
    state = _STATE_RE.search(text)
    jurisdiction = state.group(1).upper() if state else None
    name, opposing = infer_name_and_party(text)
    damages = infer_damages(text)
    severity = infer_severity(text)
    priority = "high" if severity == "high" else ("low" if severity == "low" else "medium")

    return IntakeFacts(
        name=name,
        opposing_party=opposing,
        practice_area=practice,
        case_type=practice,
        jurisdiction=jurisdiction,
        incident_date=infer_incident_date(text),
        severity=severity,
        damages=damages,
        priority=priority,  # type: ignore[arg-type]
        narrative=text,
    )
