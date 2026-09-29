from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd


DEFAULT_WEIGHTS = {
    "industry_fit": 0.25,
    "geography_fit": 0.20,
    "business_model_fit": 0.20,
    "keyword_fit": 0.15,
    "company_size_fit": 0.10,
    "evidence_quality": 0.10,
}


@dataclass
class TargetProfile:
    industry: str
    market_profile_id: str = "custom"
    countries: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    business_models: list[str] = field(default_factory=list)
    required_keywords: list[str] = field(default_factory=list)
    excluded_keywords: list[str] = field(default_factory=list)
    min_company_size: int | None = None
    max_company_size: int | None = None
    target_roles: list[str] = field(default_factory=list)
    search_archetypes: list[str] = field(default_factory=list)
    value_proposition: str = ""
    weights: dict[str, float] = field(default_factory=lambda: DEFAULT_WEIGHTS.copy())


ALIASES = {
    "company": "company_name",
    "name": "company_name",
    "organization": "company_name",
    "employees": "company_size",
    "employee_count": "company_size",
    "sector": "industry",
    "company_type": "business_model",
    "url": "source_url",
    "website": "source_url",
    "title": "source_title",
    "snippet": "source_snippet",
    "description": "source_snippet",
}


def _text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _norm(value) -> str:
    return " ".join(_text(value).lower().replace("/", " ").replace("-", " ").split())


def _tokens(values: Iterable[str]) -> list[str]:
    return [_norm(value) for value in values if _norm(value)]


def normalize_candidate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    rename = {}
    for column in normalized.columns:
        key = _norm(column).replace(" ", "_")
        rename[column] = ALIASES.get(key, key)
    normalized = normalized.rename(columns=rename)

    defaults = {
        "company_name": "",
        "country": "",
        "region": "",
        "industry": "",
        "business_model": "",
        "company_size": pd.NA,
        "source_title": "",
        "source_snippet": "",
        "source_url": "",
        "discovery_query": "",
    }
    for column, default in defaults.items():
        if column not in normalized.columns:
            normalized[column] = default

    normalized["company_size"] = pd.to_numeric(
        normalized["company_size"], errors="coerce"
    )
    return normalized


def build_search_queries(profile: TargetProfile, max_queries: int = 8) -> list[str]:
    industry = _text(profile.industry)
    markets = profile.countries or profile.regions or [""]
    models = [item for item in profile.business_models if _text(item)]
    archetypes = [item for item in profile.search_archetypes if _text(item)]
    keywords = [item for item in profile.required_keywords if _text(item)]

    queries: list[str] = []

    def add(parts: list[str]) -> None:
        query = " ".join(part for part in parts if _text(part)).strip()
        if query and query not in queries and len(queries) < max_queries:
            queries.append(query)

    for market in markets:
        add([industry, market])

    discovery_terms = archetypes or models
    for index, term in enumerate(discovery_terms):
        market = markets[index % len(markets)] if markets else ""
        keyword = keywords[index % len(keywords)] if keywords else ""
        add([term, industry, keyword, market])
        if len(queries) >= max_queries:
            return queries

    for index, model in enumerate(models):
        market = markets[index % len(markets)] if markets else ""
        keyword = keywords[index % len(keywords)] if keywords else ""
        add([model, keyword, market])
        if len(queries) >= max_queries:
            return queries

    for index, keyword in enumerate(keywords):
        market = markets[index % len(markets)] if markets else ""
        add([industry, keyword, market])
        if len(queries) >= max_queries:
            return queries

    return queries[:max_queries]

def _contains_any(haystack: str, needles: Iterable[str]) -> bool:
    h = _norm(haystack)
    return any(needle in h for needle in _tokens(needles))


def _match_score(value: str, targets: Iterable[str]) -> tuple[float | None, list[str]]:
    target_tokens = _tokens(targets)
    value_norm = _norm(value)
    if not target_tokens:
        return None, []
    if not value_norm:
        return None, []

    matched = [target for target in target_tokens if target in value_norm or value_norm in target]
    if matched:
        return 100.0, matched
    return 20.0, []


def _keyword_score(evidence: str, required_keywords: Iterable[str]) -> tuple[float | None, list[str]]:
    required = _tokens(required_keywords)
    if not required:
        return None, []
    if not _norm(evidence):
        return None, []

    evidence_norm = _norm(evidence)
    matched = [keyword for keyword in required if keyword in evidence_norm]
    count = len(matched)

    if count == 0:
        score = 20.0
    elif count == 1:
        score = 55.0
    elif count == 2:
        score = 75.0
    elif count == 3:
        score = 90.0
    else:
        score = 100.0

    return score, matched

def _company_size_score(value, minimum: int | None, maximum: int | None) -> float | None:
    if minimum is None and maximum is None:
        return None

    try:
        size = float(value)
    except Exception:
        return None

    if pd.isna(size):
        return None

    if minimum is not None and size < minimum:
        if minimum <= 0:
            return 100.0
        return round(max(20.0, (size / minimum) * 100), 1)

    if maximum is not None and size > maximum:
        if size <= 0:
            return 20.0
        return round(max(20.0, (maximum / size) * 100), 1)

    return 100.0


def _evidence_quality(row: pd.Series) -> float:
    has_url = bool(_text(row.get("source_url")))
    has_title = bool(_text(row.get("source_title")))
    snippet_length = len(_text(row.get("source_snippet")))

    if has_url and has_title and snippet_length >= 120:
        return 100.0
    if has_url and snippet_length >= 60:
        return 85.0
    if has_url and (has_title or snippet_length):
        return 70.0
    if has_title or snippet_length:
        return 50.0
    return 20.0


def _confidence_label(score: float) -> str:
    if score >= 75:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def _recommended_action(score: float, confidence: float) -> str:
    if score >= 80 and confidence >= 65:
        return "Move to Qualification"
    if score >= 65:
        return "Research & Validate"
    if score >= 50:
        return "Monitor / Enrich"
    return "Low Priority"


def _professional_setting_signal(evidence: str, industry: str) -> str:
    if "medical aesthetic" not in _norm(industry):
        return ""

    normalized = _norm(evidence)
    medical_terms = [
        "medico",
        "medical",
        "physician",
        "doctor",
        "dermatolog",
        "chirurg",
        "clinica",
        "clinic",
        "direttore sanitario",
    ]
    aesthetic_terms = [
        "estetista",
        "esthetician",
        "beautician",
        "centro estetico",
        "beauty clinic",
        "medical spa",
        "med spa",
    ]

    if any(term in normalized for term in medical_terms):
        return "Medical-setting signal observed"
    if any(term in normalized for term in aesthetic_terms):
        return "Professional/device eligibility to validate"
    return "Professional setting unknown"


def score_candidate(row: pd.Series, profile: TargetProfile) -> dict:
    evidence = " ".join(
        [
            _text(row.get("company_name")),
            _text(row.get("industry")),
            _text(row.get("business_model")),
            _text(row.get("country")),
            _text(row.get("region")),
            _text(row.get("source_title")),
            _text(row.get("source_snippet")),
        ]
    )

    excluded_matches = [
        keyword for keyword in _tokens(profile.excluded_keywords)
        if keyword in _norm(evidence)
    ]

    industry_source = " ".join([
        _text(row.get("industry")),
        _text(row.get("source_title")),
        _text(row.get("source_snippet")),
    ])
    industry_score, industry_matches = _match_score(
        industry_source, [profile.industry] if profile.industry else []
    )

    geo_source = " ".join([
        _text(row.get("country")),
        _text(row.get("region")),
        _text(row.get("source_title")),
        _text(row.get("source_snippet")),
    ])
    geography_score, geography_matches = _match_score(
        geo_source, list(profile.countries) + list(profile.regions)
    )

    business_source = " ".join([
        _text(row.get("business_model")),
        _text(row.get("source_title")),
        _text(row.get("source_snippet")),
    ])
    business_score, business_matches = _match_score(
        business_source, profile.business_models
    )

    keyword_score, keyword_matches = _keyword_score(
        evidence, profile.required_keywords
    )

    size_score = _company_size_score(
        row.get("company_size"),
        profile.min_company_size,
        profile.max_company_size,
    )

    evidence_score = _evidence_quality(row)

    component_scores = {
        "industry_fit": industry_score,
        "geography_fit": geography_score,
        "business_model_fit": business_score,
        "keyword_fit": keyword_score,
        "company_size_fit": size_score,
        "evidence_quality": evidence_score,
    }

    active_weights = {
        key: profile.weights.get(key, 0.0)
        for key, value in component_scores.items()
        if value is not None and profile.weights.get(key, 0.0) > 0
    }
    total_weight = sum(active_weights.values()) or 1.0

    weighted = {
        key: round(component_scores[key] * (weight / total_weight), 2)
        for key, weight in active_weights.items()
    }
    discovery_score = round(sum(weighted.values()), 1)

    if excluded_matches:
        discovery_score = min(discovery_score, 25.0)

    evidence_dimensions = [
        bool(_text(row.get("industry"))) or bool(industry_matches),
        bool(_text(row.get("country"))) or bool(_text(row.get("region"))) or bool(geography_matches),
        bool(_text(row.get("business_model"))) or bool(business_matches),
        bool(_text(row.get("company_size"))),
        bool(_text(row.get("source_url"))),
        bool(_text(row.get("source_snippet"))),
    ]
    coverage = sum(evidence_dimensions) / len(evidence_dimensions)
    confidence_score = round((coverage * 70) + (evidence_score * 0.30), 1)

    reasons = []
    if industry_matches:
        reasons.append("industry match")
    if geography_matches:
        reasons.append("target geography")
    if business_matches:
        reasons.append("business-model fit")
    if keyword_matches:
        reasons.append("keyword evidence")
    if size_score is not None and size_score >= 80:
        reasons.append("company-size fit")
    if not reasons:
        reasons.append("limited verified fit signals")

    unknowns = []
    if not _text(row.get("industry")):
        unknowns.append("industry")
    if not _text(row.get("country")) and not _text(row.get("region")):
        unknowns.append("geography")
    if not _text(row.get("business_model")):
        unknowns.append("business model")
    if pd.isna(row.get("company_size")):
        unknowns.append("company size")

    return {
        "discovery_score": discovery_score,
        "confidence_score": confidence_score,
        "confidence": _confidence_label(confidence_score),
        "recommended_action": "Exclude" if excluded_matches else _recommended_action(
            discovery_score, confidence_score
        ),
        "why_relevant": ", ".join(reasons),
        "matched_keywords": ", ".join(keyword_matches),
        "excluded_matches": ", ".join(excluded_matches),
        "unknowns_to_validate": ", ".join(unknowns),
        "professional_setting": _professional_setting_signal(evidence, profile.industry),
        "score_breakdown": component_scores,
    }


def screen_candidates(df: pd.DataFrame, profile: TargetProfile) -> pd.DataFrame:
    candidates = normalize_candidate_dataframe(df)

    rows = []
    for _, row in candidates.iterrows():
        result = score_candidate(row, profile)
        merged = row.to_dict()
        merged["market_profile_id"] = profile.market_profile_id
        merged["source_stage"] = "IDENTIFY"
        merged.update(result)
        rows.append(merged)

    ranked = pd.DataFrame(rows)
    if ranked.empty:
        return ranked

    ranked = ranked.sort_values(
        ["discovery_score", "confidence_score"],
        ascending=[False, False],
    ).reset_index(drop=True)
    return ranked


def qualification_handoff(ranked: pd.DataFrame) -> pd.DataFrame:
    handoff = pd.DataFrame()
    handoff["market_profile_id"] = ranked.get("market_profile_id", "")
    handoff["source_stage"] = "IDENTIFY"
    handoff["company_name"] = ranked.get("company_name", "")
    handoff["country"] = ranked.get("country", "")
    handoff["region"] = ranked.get("region", "")
    handoff["industry"] = ranked.get("industry", "")
    handoff["company_size"] = ranked.get("company_size", pd.NA)
    handoff["estimated_deal_value_usd"] = 0
    handoff["engagement_signal"] = "cold"
    handoff["discovery_score"] = ranked.get("discovery_score", 0)
    handoff["discovery_confidence"] = ranked.get("confidence", "")
    handoff["discovery_source_url"] = ranked.get("source_url", "")
    handoff["requires_manual_qualification"] = True
    return handoff
