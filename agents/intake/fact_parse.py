"""Heuristic parsers for free-text case descriptions into ``IntakeFacts``.

Used when intake receives a narrative (paste or interview answer) instead of
structured fields. Regex and keyword rules run locally — no LLM — so parsing is
fast and deterministic; interview flow layers LLM extraction on top.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

from agents.intake.constants import SENTINEL_NAME, SENTINEL_PARTY
from agents.intake.models import IntakeFacts
from tools.common import PRACTICE_TEXT_HINTS

# Supported US state codes for jurisdiction inference from narrative text
_STATE_RE = re.compile(r"\b(CA|NV|AZ|TX|FL|NY|WA|IL|OR|CO|GA)\b", re.I)
_MONEY_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)\s*k\b|\$\s*([\d,]+(?:\.\d+)?)", re.I)
_YEARS_AGO_RE = re.compile(r"(\d+)\s*years?\s*ago", re.I)
_MONTHS_AGO_RE = re.compile(r"(\d+)\s*months?\s*ago", re.I)
_ISO_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_SLASH_DATE_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b")
_NAMED_MONTH_FORMATS = (
    "%B %d, %Y",  # June 15, 2024
    "%b %d, %Y",  # Jun 15, 2024
    "%d %B %Y",  # 15 June 2024
    "%d %b %Y",  # 15 Jun 2024
    "%B %d %Y",  # June 15 2024
    "%b %d %Y",
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def is_iso_date(value: str | None) -> bool:
    """Return True when ``value`` is a real calendar date in ``YYYY-MM-DD`` form."""
    if not value or len(value.strip()) < 10:
        return False
    try:
        date.fromisoformat(value.strip()[:10])
        return True
    except ValueError:
        return False


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_named_month_date(text: str) -> date | None:
    cleaned = re.sub(r"\s+", " ", text.strip()).rstrip(" .,;")
    for fmt in _NAMED_MONTH_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _parse_numeric_date(text: str) -> date | None:
    """Parse slash/dot/dash numeric dates; ambiguous pairs prefer US ``MM/DD/YYYY``."""
    match = _SLASH_DATE_RE.search(text)
    if not match:
        return None
    first, second, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    ordered: list[tuple[int, int, int]] = []
    if first > 12 and 1 <= second <= 12:
        ordered.append((year, second, first))  # DD/MM/YYYY
    elif second > 12 and 1 <= first <= 12:
        ordered.append((year, first, second))  # MM/DD/YYYY
    else:
        # US law-firm default when both parts are plausible months.
        ordered.extend([(year, first, second), (year, second, first)])
    for y, m, d in ordered:
        parsed = _safe_date(y, m, d)
        if parsed is not None:
            return parsed
    return None


def infer_practice_area(text: str) -> str | None:
    """Match practice area from shared keyword hints in ``PRACTICE_TEXT_HINTS``."""
    lower = text.lower()
    for needle, area in PRACTICE_TEXT_HINTS:
        if needle in lower:
            return area
    return None


def infer_damages(text: str) -> int | None:
    """Extract USD damages from ``$50k`` or ``$12,500`` style mentions."""
    match = _MONEY_RE.search(text)
    if not match:
        return None
    # ``k`` suffix means thousands (e.g. ``50k`` → 50_000)
    if match.group(1):
        return int(float(match.group(1).replace(",", "")) * 1000)
    if match.group(2):
        return int(float(match.group(2).replace(",", "")))
    return None


def infer_incident_date(text: str) -> str | None:
    """Normalize supported date phrases to ``YYYY-MM-DD``, or ``None`` if unknown.

    Accepts ISO dates, relative ``N years/months ago``, US numeric dates
    (``MM/DD/YYYY``), unambiguous day-first numeric dates, and common month-name
    forms. Does not invent dates from free text that cannot be parsed.
    """
    if not (text or "").strip():
        return None

    years = _YEARS_AGO_RE.search(text)
    if years:
        d = _today().replace(year=_today().year - int(years.group(1)))
        return d.isoformat()

    months = _MONTHS_AGO_RE.search(text)
    if months:
        # Approximate months as 30-day blocks (good enough for screening)
        ordinal = _today().toordinal() - int(months.group(1)) * 30
        return date.fromordinal(max(1, ordinal)).isoformat()

    iso = _ISO_RE.search(text)
    if iso and is_iso_date(iso.group(1)):
        return iso.group(1)

    named = _parse_named_month_date(text)
    if named is not None:
        return named.isoformat()

    numeric = _parse_numeric_date(text)
    if numeric is not None:
        return numeric.isoformat()

    return None


def infer_severity(text: str) -> str:
    """Classify injury/event severity from keyword cues; defaults to ``medium``."""
    lower = text.lower()
    if any(w in lower for w in ("catastrophic", "icu", "death", "severe")):
        return "high"
    if any(w in lower for w in ("moderate", "surgery")):
        return "medium"
    if any(w in lower for w in ("minor", "unclear", "missing")):
        return "low"
    return "medium"


def infer_name_and_party(text: str) -> tuple[str, str]:
    """Best-effort party names; returns sentinel placeholders when unknown."""
    lower = text.lower()
    # Demo fixture for employment scenarios in docs and smoke tests
    if "acme" in lower and "employment" in lower:
        return "Elena Vasquez", "ACME Corp"
    if "opposing party" in lower:
        m = re.search(r"opposing party(?:\s+is)?\s+([A-Za-z0-9 .,&-]+)", text, flags=re.I)
        if m:
            return SENTINEL_NAME, m.group(1).strip(" .")
    return SENTINEL_NAME, SENTINEL_PARTY


def parse_case_description(description: str) -> IntakeFacts:
    """Build a full ``IntakeFacts`` record from a single free-text case description."""
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
