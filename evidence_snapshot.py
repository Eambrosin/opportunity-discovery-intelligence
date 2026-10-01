from __future__ import annotations

import re
from typing import Iterable


NAVIGATION_LABELS = {
    "prenota ora",
    "news",
    "chi siamo",
    "il nostro spazio",
    "odontoiatria",
    "dietologia e nutrizione",
    "ortodonzia",
    "gastroenterologia",
    "dermatologia",
    "medicina estetica",
    "fisioterapia",
    "altre specialità",
    "altre specialita",
    "il nostro team",
    "i nostri pazienti",
    "odontoiatria digitale",
    "strumenti high tech",
    "materiali",
    "home",
    "contatti",
    "contact",
    "about",
}

COMMERCIAL_TERMS = (
    "medicina estetica",
    "medico estetico",
    "chirurgia estetica",
    "chirurgo estetico",
    "dermatologia estetica",
    "filler",
    "acido ialuronico",
    "biorevitalizzazione",
    "biostimolazione",
    "peeling",
    "foto-ringiovanimento",
    "fotoringiovanimento",
    "ringiovanimento",
    "tossina botulinica",
    "botox",
    "lifting",
    "criolipolisi",
    "hifu",
    "laser",
    "radiofrequenza",
    "cellulite",
    "rimodellamento corpo",
    "body contouring",
    "trattamenti non chirurgici",
    "trattamento non chirurgico",
    "skin rejuvenation",
    "skin regeneration",
)

ADDRESS_PREFIXES = (
    "via ",
    "viale ",
    "piazza ",
    "corso ",
    "largo ",
    "strada ",
    "vicolo ",
)


def _normalize(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    return text.strip(" .,:;|-—–")


def _clean_line(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^\s*#{1,6}\s*", "", text)
    text = re.sub(r"^\s*[-*•]+\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_source_text(source_text: str) -> list[str]:
    text = str(source_text or "").replace(" | ", "\n")
    lines = [_clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    if len(lines) <= 1 and len(text) > 450:
        sentence_parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9])", text)
        lines = [_clean_line(part) for part in sentence_parts if _clean_line(part)]

    return lines


def _dedupe(lines: Iterable[str]) -> list[str]:
    seen = set()
    output = []
    for line in lines:
        key = _normalize(line)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(line)
    return output


def _is_navigation_line(line: str) -> bool:
    normalized = _normalize(line)
    if normalized in NAVIGATION_LABELS:
        return True

    if len(normalized.split()) <= 4 and normalized in {
        "sostenibilità",
        "sostenibilita",
        "plus sostenibilità",
        "plus sostenibilita",
    }:
        return True

    return False


def _is_contact_line(line: str) -> bool:
    normalized = _normalize(line)

    if "@" in line:
        return True
    if re.search(r"\b(?:tel|telefono|phone)\.?\s*[:.]?\s*\+?[\d\s()./-]{6,}", line, re.I):
        return True
    if re.search(r"\+?\d[\d\s()./-]{7,}\d", line):
        return True
    if normalized.startswith(ADDRESS_PREFIXES):
        return True
    if any(f" {prefix}" in f" {normalized}" for prefix in ADDRESS_PREFIXES):
        return True

    return False


def _is_commercial_evidence(line: str) -> bool:
    normalized = _normalize(line)
    return any(term in normalized for term in COMMERCIAL_TERMS)


def _trim(line: str, max_chars: int = 420) -> str:
    if len(line) <= max_chars:
        return line
    return line[: max_chars - 1].rstrip() + "…"


def build_relevant_evidence_snapshot(
    source_text: str,
    *,
    max_contact_lines: int = 4,
    max_evidence_lines: int = 7,
) -> dict:
    lines = _split_source_text(source_text)

    contact_lines = []
    commercial_lines = []

    for line in lines:
        if _is_navigation_line(line):
            continue

        if _is_contact_line(line):
            contact_lines.append(_trim(line))
            continue

        if _is_commercial_evidence(line):
            commercial_lines.append(_trim(line))

    contact_lines = _dedupe(contact_lines)[:max_contact_lines]
    commercial_lines = _dedupe(commercial_lines)[:max_evidence_lines]

    compact = " ".join(lines)
    fallback_preview = _trim(compact, 320) if compact else ""

    return {
        "contact_lines": contact_lines,
        "commercial_evidence": commercial_lines,
        "fallback_preview": fallback_preview,
        "source_line_count": len(lines),
        "relevant_line_count": len(contact_lines) + len(commercial_lines),
    }
