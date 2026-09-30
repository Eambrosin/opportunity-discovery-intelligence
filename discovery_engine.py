from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd


COUNTRY_TO_COMMERCIAL_REGION = {
    "Italy": "EU",
    "France": "EU",
    "Spain": "EU",
    "Portugal": "EU",
    "Germany": "EU",
    "Austria": "EU",
    "Brazil": "LATAM",
    "Mexico": "LATAM",
    "Colombia": "LATAM",
    "Argentina": "LATAM",
    "UAE": "MENA",
    "United Arab Emirates": "MENA",
    "Saudi Arabia": "MENA",
    "United States": "NA",
    "USA": "NA",
    "Canada": "NA",
}


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


def _medical_aesthetics_entity_classification(
    row: pd.Series,
    evidence: str,
    profile: TargetProfile,
) -> dict:
    if profile.market_profile_id != "medical_aesthetics":
        identity_ready = row.get("qualification_ready", True)
        return {
            "commercial_track": "Target Account",
            "target_account_ready": bool(identity_ready),
            "target_account_reason": "Generic market account workflow",
        }

    identity_raw = row.get("qualification_ready", True)
    if isinstance(identity_raw, bool):
        identity_ready = identity_raw
    else:
        identity_ready = str(identity_raw).strip().lower() in {"true", "1", "yes"}

    identity_status = _norm(row.get("account_identity_status"))
    normalized = _norm(evidence)

    if not identity_ready or any(
        token in identity_status
        for token in ["directory marketplace", "content document", "account identity unclear"]
    ):
        return {
            "commercial_track": "Held-back Research Result",
            "target_account_ready": False,
            "target_account_reason": "Account identity is not strong enough for qualification",
        }

    practitioner_terms = [
        "dott.",
        "dott ",
        "dottore",
        "dottor",
        "dottoressa",
        "prof.",
        "prof ",
        "dr.",
        "medico estetico",
        "aesthetic physician",
        "dermatologo",
        "dermatologist",
        "chirurgo plastico",
        "plastic surgeon",
    ]
    provider_terms = [
        "clinica",
        "clinic",
        "centro medico",
        "medical center",
        "studio medico",
        "medical practice",
        "poliambulator",
        "medicina estetica",
        "dermatologia estetica",
        "chirurgia plastica",
        "medical spa",
        "med spa",
    ]
    aesthetic_center_terms = [
        "centro estetico",
        "beauty clinic",
        "istituto di bellezza",
        "estetica avanzata",
        "esthetician",
        "estetista",
    ]
    supplier_terms = [
        "manufacturer",
        "produttore",
        "distributore",
        "distributor",
        "medical device",
        "dispositivo medico",
        "apparecchiature",
        "elettromedicale",
        "tecnologie medicali",
        "aesthetic technology",
        "laser manufacturer",
        "made in italy",
        "brevetti",
        "academy",
        "formazione per medici",
    ]

    practitioner = any(term in normalized for term in practitioner_terms)
    provider = any(term in normalized for term in provider_terms)
    aesthetic_center = any(term in normalized for term in aesthetic_center_terms)
    supplier = any(term in normalized for term in supplier_terms)

    identity_text = _norm(
        " ".join(
            [
                _text(row.get("company_name")),
                _text(row.get("source_title")),
            ]
        )
    )
    supplier_primary = any(term in identity_text for term in supplier_terms)
    provider_identity = any(term in identity_text for term in provider_terms)
    practitioner_identity = any(term in identity_text for term in practitioner_terms)
    aesthetic_identity = any(term in identity_text for term in aesthetic_center_terms)

    if supplier and (
        supplier_primary
        or not (practitioner_identity or provider_identity or aesthetic_identity)
    ):
        return {
            "commercial_track": "Partner / Vendor Candidate",
            "target_account_ready": False,
            "target_account_reason": "Looks more like a supplier, manufacturer or partner than a clinic/practice account",
        }

    if practitioner:
        return {
            "commercial_track": "Practitioner Target",
            "target_account_ready": True,
            "target_account_reason": "Relevant medical-aesthetics practitioner signal observed",
        }

    if provider:
        return {
            "commercial_track": "Clinic / Medical Practice Target",
            "target_account_ready": True,
            "target_account_reason": "Relevant clinic or medical-practice signal observed",
        }

    if aesthetic_center:
        return {
            "commercial_track": "Aesthetic Center — Eligibility Validation",
            "target_account_ready": True,
            "target_account_reason": "Relevant aesthetic-center signal observed; device eligibility requires validation",
        }

    return {
        "commercial_track": "Held-back Research Result",
        "target_account_ready": False,
        "target_account_reason": "No sufficiently clear clinic, practitioner or aesthetic-center signal",
    }


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

    if profile.market_profile_id == "medical_aesthetics":
        industry_evidence_terms = [
            "medicina estetica",
            "medico estetico",
            "aesthetic medicine",
            "aesthetic physician",
            "dermatologia estetica",
            "chirurgia plastica",
            "plastic surgery",
        ]
        observed_industry_terms = [
            term
            for term in industry_evidence_terms
            if term in _norm(industry_source)
        ]
        if observed_industry_terms:
            industry_score = 100.0
            industry_matches = list(
                dict.fromkeys(industry_matches + observed_industry_terms)
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

    entity_classification = _medical_aesthetics_entity_classification(
        row,
        evidence,
        profile,
    )

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
        "commercial_track": entity_classification["commercial_track"],
        "target_account_ready": entity_classification["target_account_ready"],
        "target_account_reason": entity_classification["target_account_reason"],
        "score_breakdown": component_scores,
    }


def screen_candidates(df: pd.DataFrame, profile: TargetProfile) -> pd.DataFrame:
    candidates = normalize_candidate_dataframe(df)

    rows = []
    for _, row in candidates.iterrows():
        result = score_candidate(row, profile)
        merged = row.to_dict()
        merged["schema_version"] = "1.0"
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


def qualification_handoff(
    ranked: pd.DataFrame,
    profile: TargetProfile | None = None,
) -> pd.DataFrame:
    working = ranked.copy()

    def aligned_series(column: str, default="") -> pd.Series:
        if column in working.columns:
            return working[column].copy()
        return pd.Series([default] * len(working), index=working.index)

    if "qualification_ready" in working.columns:
        ready_raw = aligned_series("qualification_ready", False)
        ready_mask = (
            ready_raw.fillna(False)
            .map(
                lambda value: (
                    value
                    if isinstance(value, bool)
                    else str(value).strip().lower() in {"true", "1", "yes"}
                )
            )
        )
        working = working[ready_mask].copy()

    if working.empty:
        return pd.DataFrame()

    profile_country = ""
    if profile is not None and len(profile.countries) == 1:
        profile_country = profile.countries[0]

    profile_industry = profile.industry if profile is not None else ""

    handoff = pd.DataFrame(index=working.index)
    handoff["schema_version"] = pd.Series(
        ["1.0"] * len(working),
        index=working.index,
    )
    handoff["market_profile_id"] = aligned_series("market_profile_id", "")
    handoff["source_stage"] = pd.Series(
        ["IDENTIFY"] * len(working),
        index=working.index,
    )
    handoff["company_name"] = aligned_series("company_name", "").fillna("").astype(str)

    observed_country = (
        aligned_series("country", "")
        .fillna("")
        .astype(str)
        .str.strip()
    )
    handoff["country"] = observed_country.mask(
        observed_country.eq(""),
        profile_country,
    )
    handoff["country_basis"] = observed_country.map(
        lambda value: "source observed" if value else "target-market context"
    )

    observed_region = (
        aligned_series("region", "")
        .fillna("")
        .astype(str)
        .str.strip()
    )
    derived_region = handoff["country"].map(
        COUNTRY_TO_COMMERCIAL_REGION
    ).fillna("")
    handoff["region"] = observed_region.mask(
        observed_region.eq(""),
        derived_region,
    )
    handoff["region_basis"] = observed_region.map(
        lambda value: "source observed" if value else "derived from country context"
    )

    observed_industry = (
        aligned_series("industry", "")
        .fillna("")
        .astype(str)
        .str.strip()
    )
    handoff["industry"] = observed_industry.mask(
        observed_industry.eq(""),
        profile_industry,
    )
    handoff["industry_basis"] = observed_industry.map(
        lambda value: "source observed" if value else "market-profile context"
    )

    company_size = pd.to_numeric(
        aligned_series("company_size", pd.NA),
        errors="coerce",
    )
    handoff["company_size"] = company_size
    handoff["company_size_status"] = company_size.notna().map(
        {True: "observed", False: "unknown"}
    )

    handoff["estimated_deal_value_usd"] = 0.0
    handoff["deal_value_status"] = "unknown"
    handoff["engagement_signal"] = ""
    handoff["engagement_status"] = "unverified"

    handoff["discovery_score"] = pd.to_numeric(
        aligned_series("discovery_score", 0),
        errors="coerce",
    ).fillna(0)
    handoff["discovery_confidence"] = aligned_series("confidence", "")
    handoff["discovery_source_url"] = aligned_series("source_url", "")
    handoff["account_identity_score"] = pd.to_numeric(
        aligned_series("account_identity_score", pd.NA),
        errors="coerce",
    )
    handoff["account_identity_status"] = aligned_series(
        "account_identity_status",
        "",
    )

    optional_fields = [
        "territory_profile_id",
        "vendor_profile_id",
        "territory_region",
        "territory_province",
        "territory_city",
        "territory_cluster_id",
        "territory_location_confidence",
        "territory_location_basis",
        "account_opportunity_score",
        "territory_status",
        "professional_setting",
        "observed_technology_axes",
        "technology_evidence",
        "technology_validation_questions",
        "account_website",
        "website_evidence_status",
        "website_match_score",
        "public_phone",
        "public_email",
        "public_address",
        "public_contact_form",
        "contact_channel_status",
        "enrichment_fit_signals",
        "account_data_completeness",
        "enrichment_status",
        "enrichment_source_url",
        "enrichment_source_urls",
        "enrichment_evidence",
        "decision_maker_candidate_found",
        "decision_maker_verified",
        "decision_maker_name",
        "decision_maker_headline",
        "decision_maker_linkedin",
        "decision_maker_confidence",
        "decision_maker_relevance_score",
        "qualification_readiness_score",
        "qualification_readiness_status",
        "qualification_readiness_evidence",
        "sales_motion",
        "buyer_access_status",
        "commercial_hypothesis",
        "commercial_angle",
        "next_best_action",
        "qualification_questions",
        "sales_evidence_gaps",
        "commercial_risk_flags",
        "sales_intelligence_basis",
    ]
    for field_name in optional_fields:
        if field_name in working.columns:
            handoff[field_name] = working[field_name]

    handoff["requires_manual_qualification"] = True
    return handoff.reset_index(drop=True)

