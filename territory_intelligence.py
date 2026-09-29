from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import pandas as pd


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
    return " ".join(
        _text(value)
        .lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace("’", "'")
        .split()
    )


def _contains(text: str, term: str) -> bool:
    return _norm(term) in _norm(text)


def selected_clusters(
    territory: dict,
    cluster_ids: Iterable[str] | None = None,
) -> list[dict]:
    clusters = territory.get("clusters", [])
    if not cluster_ids:
        return list(clusters)
    wanted = set(cluster_ids)
    return [cluster for cluster in clusters if cluster.get("cluster_id") in wanted]


def build_territory_search_queries(
    profile,
    territory: dict,
    cluster_ids: Iterable[str],
    max_queries: int = 12,
) -> list[str]:
    clusters = selected_clusters(territory, cluster_ids)
    archetypes = [item for item in profile.search_archetypes if _text(item)]
    keywords = [item for item in profile.required_keywords if _text(item)]

    if not archetypes:
        archetypes = [profile.industry or "business"]
    if not keywords:
        keywords = [""]

    italian_medical_terms = [
        "clinica medicina estetica",
        "medico estetico",
        "dermatologo medicina estetica",
        "chirurgo plastico medicina estetica",
        "centro estetico tecnologie",
    ]
    german_medical_terms = [
        "ästhetische medizin",
        "ästhetischer arzt",
        "dermatologie ästhetik",
        "schönheitsklinik",
    ]

    queries: list[str] = []

    for index, cluster in enumerate(clusters):
        if len(queries) >= max_queries:
            break

        cities = cluster.get("cities", [])
        location = cities[0] if cities else cluster.get("province", "")
        region = cluster.get("region", "")

        local_terms = german_medical_terms if "de" in cluster.get("languages", []) and index % 2 else italian_medical_terms
        archetype = local_terms[index % len(local_terms)] if profile.market_profile_id == "medical_aesthetics" else archetypes[index % len(archetypes)]
        keyword = keywords[index % len(keywords)]

        source_preference = ""
        if profile.market_profile_id == "medical_aesthetics":
            source_preference = (
                "offizielle website"
                if "de" in cluster.get("languages", [])
                else "sito ufficiale"
            )

        query = " ".join(
            part
            for part in [
                archetype,
                keyword,
                location,
                region,
                territory.get("country", "Italy"),
                source_preference,
            ]
            if _text(part)
        ).strip()

        if query and query not in queries:
            queries.append(query)

    return queries[:max_queries]


def infer_territory_location(row: pd.Series | dict, territory: dict) -> dict:
    evidence = " ".join(
        [
            _text(row.get("company_name")),
            _text(row.get("country")),
            _text(row.get("region")),
            _text(row.get("source_title")),
            _text(row.get("source_snippet")),
            _text(row.get("source_url")),
        ]
    )
    query = _text(row.get("discovery_query"))

    best = None

    for cluster in territory.get("clusters", []):
        city_matches = [city for city in cluster.get("cities", []) if _contains(evidence, city)]
        province_matches = [
            alias
            for alias in cluster.get("province_aliases", [])
            if _contains(evidence, alias)
        ]
        region_match = _contains(evidence, cluster.get("region", ""))

        if city_matches:
            candidate = {
                "territory_region": cluster["region"],
                "territory_province": cluster["province"],
                "territory_city": city_matches[0],
                "territory_cluster_id": cluster["cluster_id"],
                "territory_location_confidence": 100.0,
                "territory_location_basis": "Source-observed city",
            }
            return candidate

        if province_matches:
            candidate = {
                "territory_region": cluster["region"],
                "territory_province": cluster["province"],
                "territory_city": "",
                "territory_cluster_id": cluster["cluster_id"],
                "territory_location_confidence": 88.0,
                "territory_location_basis": "Source-observed province",
            }
            if best is None or candidate["territory_location_confidence"] > best["territory_location_confidence"]:
                best = candidate

        elif region_match:
            candidate = {
                "territory_region": cluster["region"],
                "territory_province": "",
                "territory_city": "",
                "territory_cluster_id": "",
                "territory_location_confidence": 72.0,
                "territory_location_basis": "Source-observed region",
            }
            if best is None or candidate["territory_location_confidence"] > best["territory_location_confidence"]:
                best = candidate

    if best:
        return best

    for cluster in territory.get("clusters", []):
        query_terms = (
            list(cluster.get("cities", []))
            + list(cluster.get("province_aliases", []))
            + [cluster.get("region", "")]
        )
        if any(term and _contains(query, term) for term in query_terms):
            cities = [city for city in cluster.get("cities", []) if _contains(query, city)]
            return {
                "territory_region": cluster["region"],
                "territory_province": cluster["province"],
                "territory_city": cities[0] if cities else "",
                "territory_cluster_id": cluster["cluster_id"],
                "territory_location_confidence": 55.0,
                "territory_location_basis": "Search-scope inferred; verify location",
            }

    return {
        "territory_region": "",
        "territory_province": "",
        "territory_city": "",
        "territory_cluster_id": "",
        "territory_location_confidence": 20.0,
        "territory_location_basis": "Location not established",
    }


def extract_technology_signals(
    row: pd.Series | dict,
    vendor_profile: dict | None,
) -> dict:
    if not vendor_profile:
        return {
            "observed_technology_axes": "",
            "technology_signal_count": 0,
            "technology_evidence": "",
            "technology_validation_questions": "",
        }

    evidence = " ".join(
        [
            _text(row.get("company_name")),
            _text(row.get("source_title")),
            _text(row.get("source_snippet")),
            _text(row.get("business_model")),
        ]
    )

    observed = []
    matched_terms = []

    for axis, terms in vendor_profile.get("technology_axes", {}).items():
        axis_matches = [term for term in terms if _contains(evidence, term)]
        if axis_matches:
            observed.append(axis)
            matched_terms.extend(axis_matches[:3])

    questions = []
    if not observed:
        questions.append("Current treatment and technology portfolio")
    questions.extend(
        [
            "Installed equipment / current provider",
            "Investment timing and decision process",
        ]
    )

    return {
        "observed_technology_axes": ", ".join(observed),
        "technology_signal_count": len(observed),
        "technology_evidence": ", ".join(dict.fromkeys(matched_terms)),
        "technology_validation_questions": ", ".join(questions),
    }


def technology_landscape(
    row: pd.Series | dict,
    vendor_profile: dict | None,
) -> pd.DataFrame:
    if not vendor_profile:
        return pd.DataFrame()

    evidence = " ".join(
        [
            _text(row.get("company_name")),
            _text(row.get("source_title")),
            _text(row.get("source_snippet")),
            _text(row.get("business_model")),
        ]
    )

    rows = []
    for axis, terms in vendor_profile.get("technology_axes", {}).items():
        matched = [term for term in terms if _contains(evidence, term)]
        rows.append(
            {
                "technology_axis": axis,
                "evidence_status": (
                    "Observed in current evidence"
                    if matched
                    else "Not observed — validate"
                ),
                "matched_terms": ", ".join(matched[:4]),
            }
        )

    return pd.DataFrame(rows)


def _professional_setting_score(value: str) -> float:
    normalized = _norm(value)
    if "medical setting signal observed" in normalized:
        return 100.0
    if "eligibility to validate" in normalized:
        return 60.0
    if "unknown" in normalized:
        return 45.0
    return 70.0


def _territory_status(
    opportunity_score: float,
    evidence_confidence: float,
    location_confidence: float,
    professional_setting: str,
) -> str:
    setting = _norm(professional_setting)

    if "eligibility to validate" in setting:
        return "Eligibility Validation"
    if location_confidence < 50:
        return "Research Location"
    if evidence_confidence < 45:
        return "Research First"
    if opportunity_score >= 82 and evidence_confidence >= 65:
        return "Find Decision Maker"
    if opportunity_score >= 68:
        return "Research & Enrich"
    return "Territory Prospect"


def apply_territory_intelligence(
    ranked: pd.DataFrame,
    territory: dict,
    vendor_profile: dict | None = None,
) -> pd.DataFrame:
    if ranked.empty:
        return ranked.copy()

    rows = []

    for _, row in ranked.iterrows():
        enriched = row.to_dict()
        location = infer_territory_location(row, territory)
        technology = extract_technology_signals(row, vendor_profile)

        discovery_score = float(row.get("discovery_score", 0) or 0)
        confidence_score = float(row.get("confidence_score", 0) or 0)
        location_confidence = float(location["territory_location_confidence"])
        setting_score = _professional_setting_score(
            _text(row.get("professional_setting"))
        )
        technology_score = min(
            100.0,
            45.0 + (technology["technology_signal_count"] * 18.0),
        )

        account_score = round(
            (discovery_score * 0.60)
            + (location_confidence * 0.15)
            + (setting_score * 0.15)
            + (technology_score * 0.10),
            1,
        )

        enriched.update(location)
        enriched.update(technology)
        enriched["territory_profile_id"] = territory.get("territory_profile_id", "")
        enriched["vendor_profile_id"] = (
            vendor_profile.get("vendor_profile_id", "")
            if vendor_profile
            else ""
        )
        enriched["account_opportunity_score"] = account_score
        enriched["territory_status"] = _territory_status(
            account_score,
            confidence_score,
            location_confidence,
            _text(row.get("professional_setting")),
        )
        rows.append(enriched)

    result = pd.DataFrame(rows)
    return result.sort_values(
        ["account_opportunity_score", "confidence_score", "discovery_score"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def contact_readiness(
    contact_row: pd.Series | dict,
    account_row: pd.Series | dict,
) -> dict:
    relevance = float(contact_row.get("contact_relevance_score", 0) or 0)
    confidence_label = _norm(contact_row.get("contact_confidence", ""))

    confidence_score = {
        "high": 100.0,
        "medium": 65.0,
        "low": 30.0,
    }.get(confidence_label, 30.0)

    has_linkedin = bool(_text(contact_row.get("linkedin_url")))
    has_headline = bool(_text(contact_row.get("headline")))
    matched_role = bool(_text(contact_row.get("matched_target_roles")))
    location_confidence = float(
        account_row.get("territory_location_confidence", 20) or 20
    )
    account_score = float(
        account_row.get("account_opportunity_score", account_row.get("discovery_score", 0))
        or 0
    )

    evidence_completeness = (
        (35 if has_linkedin else 0)
        + (25 if has_headline else 0)
        + (40 if matched_role else 0)
    )

    readiness = round(
        (relevance * 0.45)
        + (confidence_score * 0.20)
        + (evidence_completeness * 0.20)
        + (min(location_confidence, 100) * 0.15),
        1,
    )

    if readiness >= 85 and account_score >= 85 and location_confidence >= 75:
        status = "Ready for Field Visit"
    elif readiness >= 75 and account_score >= 75:
        status = "Ready for Outreach"
    elif readiness >= 55:
        status = "Verify Contact"
    else:
        status = "Research Contact"

    return {
        "contact_readiness_score": readiness,
        "contact_status": status,
    }


def enrich_contacts_with_readiness(
    contacts: pd.DataFrame,
    account_row: pd.Series | dict,
) -> pd.DataFrame:
    if contacts.empty:
        return contacts.copy()

    rows = []
    for _, contact in contacts.iterrows():
        enriched = contact.to_dict()
        enriched.update(contact_readiness(contact, account_row))
        rows.append(enriched)

    return pd.DataFrame(rows).sort_values(
        ["contact_readiness_score", "contact_relevance_score"],
        ascending=[False, False],
    ).reset_index(drop=True)


def territory_summary(
    ranked: pd.DataFrame,
    territory: dict,
) -> dict:
    if ranked.empty:
        return {
            "accounts": 0,
            "high_opportunity": 0,
            "mapped_location": 0,
            "research_coverage": 0.0,
            "eligibility_validation": 0,
        }

    accounts = len(ranked)
    mapped = int(
        (pd.to_numeric(ranked.get("territory_location_confidence", 0), errors="coerce").fillna(0) >= 50).sum()
    )
    high_opportunity = int(
        (pd.to_numeric(ranked.get("account_opportunity_score", 0), errors="coerce").fillna(0) >= 80).sum()
    )
    eligibility = int(
        (ranked.get("territory_status", pd.Series(dtype=str)).astype(str) == "Eligibility Validation").sum()
    )

    return {
        "accounts": accounts,
        "high_opportunity": high_opportunity,
        "mapped_location": mapped,
        "research_coverage": round((mapped / accounts) * 100, 1) if accounts else 0.0,
        "eligibility_validation": eligibility,
    }


def territory_breakdown(
    ranked: pd.DataFrame,
    group_by: str = "territory_region",
) -> pd.DataFrame:
    if ranked.empty or group_by not in ranked.columns:
        return pd.DataFrame()

    working = ranked.copy()
    working[group_by] = working[group_by].fillna("").astype(str)
    working = working[working[group_by].str.strip() != ""]
    if working.empty:
        return pd.DataFrame()

    rows = []
    for key, group in working.groupby(group_by):
        rows.append(
            {
                group_by: key,
                "accounts": len(group),
                "high_opportunity": int((group["account_opportunity_score"] >= 80).sum()),
                "average_opportunity_score": round(group["account_opportunity_score"].mean(), 1),
                "high_confidence": int((group["confidence"] == "High").sum()),
                "decision_maker_research_needed": int((group["territory_status"] == "Find Decision Maker").sum()),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["high_opportunity", "average_opportunity_score", "accounts"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def territory_gaps(
    ranked: pd.DataFrame,
    territory: dict,
    cluster_ids: Iterable[str],
    searched_cluster_ids: Iterable[str] | None = None,
) -> pd.DataFrame:
    clusters = selected_clusters(territory, cluster_ids)
    searched = set(searched_cluster_ids or cluster_ids)
    counts = defaultdict(int)
    high_counts = defaultdict(int)

    if not ranked.empty:
        for _, row in ranked.iterrows():
            cid = _text(row.get("territory_cluster_id"))
            if cid:
                counts[cid] += 1
                if float(row.get("account_opportunity_score", 0) or 0) >= 80:
                    high_counts[cid] += 1

    rows = []
    for cluster in clusters:
        cid = cluster["cluster_id"]
        count = counts[cid]
        high = high_counts[cid]

        if cid not in searched:
            gap = "Not searched in current run"
        elif count == 0:
            gap = "Searched; no mapped accounts yet"
        elif high == 0:
            gap = "Accounts found; no 80+ opportunity yet"
        elif high >= 3:
            gap = "Strong opportunity concentration"
        else:
            gap = "Promising; continue enrichment"

        rows.append(
            {
                "region": cluster["region"],
                "province": cluster["province"],
                "cluster_id": cid,
                "accounts_mapped": count,
                "high_opportunity": high,
                "research_gap": gap,
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["accounts_mapped", "high_opportunity", "region", "province"],
        ascending=[True, True, True, True],
    ).reset_index(drop=True)
