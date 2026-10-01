from __future__ import annotations

import re
from urllib.parse import urlparse

import pandas as pd
import requests

try:
    from web_discovery import ACCOUNT_DISCOVERY_EXCLUDE_DOMAINS
except (ImportError, AttributeError):
    # Keep account enrichment boot-safe if a deployment briefly loads modules
    # from different revisions during an incremental refresh.
    ACCOUNT_DISCOVERY_EXCLUDE_DOMAINS = [
        "fresha.com",
        "treatwell.it",
        "treatwell.com",
        "paginegialle.it",
        "miodottore.it",
        "doctoralia.it",
        "yelp.com",
        "tripadvisor.com",
        "whatclinic.com",
        "ambienteeuropa.info",
    ]


TAVILY_ENDPOINT = "https://api.tavily.com/search"

GENERIC_COMPANY_TOKENS = {
    "clinic",
    "clinica",
    "medical",
    "medico",
    "medica",
    "center",
    "centre",
    "centro",
    "studio",
    "estetica",
    "aesthetic",
    "medicine",
    "medicina",
    "italia",
    "italy",
    "srl",
    "spa",
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
    return " ".join(
        _text(value)
        .lower()
        .replace("-", " ")
        .replace("/", " ")
        .replace("’", "'")
        .split()
    )


def _domain(url: str) -> str:
    try:
        return urlparse(_text(url)).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _root_url(url: str) -> str:
    parsed = urlparse(_text(url))
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_excluded_domain(domain: str) -> bool:
    return any(
        domain == blocked or domain.endswith("." + blocked)
        for blocked in ACCOUNT_DISCOVERY_EXCLUDE_DOMAINS
    )


def _company_tokens(company_name: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9à-ÿ]+", _norm(company_name))
    meaningful = [
        token
        for token in tokens
        if len(token) >= 3 and token not in GENERIC_COMPANY_TOKENS
    ]
    return meaningful


def _token_match_ratio(company_name: str, evidence: str) -> float:
    tokens = _company_tokens(company_name)
    if not tokens:
        return 0.0
    haystack = _norm(evidence)
    matched = sum(token in haystack for token in tokens)
    return matched / len(tokens)


def _trusted_source_domain(account: dict) -> str:
    """
    Preserve a strong discovery identity during enrichment.

    Once discovery has found a direct-looking account domain with strong identity
    evidence, enrichment may add contact pages/evidence from that same domain but
    should not silently replace the account with another organization that merely
    shares a generic or geographic token.
    """
    current_domain = _text(account.get("source_domain")) or _domain(
        _text(account.get("source_url"))
    )
    if not current_domain or _is_excluded_domain(current_domain):
        return ""

    try:
        identity_score = float(account.get("account_identity_score", 0) or 0)
    except Exception:
        identity_score = 0.0

    return current_domain if identity_score >= 70 else ""


def _exact_company_phrase_match(company_name: str, evidence: str) -> bool:
    company = _norm(company_name)
    return bool(company and company in _norm(evidence))


def _extract_email(text: str) -> str:
    candidates = re.findall(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        _text(text),
        flags=re.I,
    )
    for candidate in candidates:
        lower = candidate.lower()
        if not lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return candidate
    return ""


def _normalize_phone(candidate: str) -> str:
    value = " ".join(candidate.split()).strip(" ,.;")
    digits = re.sub(r"\D", "", value)
    if not (9 <= len(digits) <= 13):
        return ""
    return value


def _extract_phone(text: str) -> str:
    value = _text(text)

    labelled = re.search(
        r"(?:tel(?:efono)?|phone|cell(?:ulare)?|whatsapp)\s*[:.]?\s*"
        r"(\+?39[\s.\-/]?(?:\d[\s.\-/]?){8,11}|"
        r"(?:0\d{1,3}|3\d{2})(?:[\s.\-/]?\d){6,10})",
        value,
        flags=re.I,
    )
    if labelled:
        phone = _normalize_phone(labelled.group(1))
        if phone:
            return phone

    italian = re.search(
        r"\b(\+39[\s.\-/]?(?:\d[\s.\-/]?){8,11})\b",
        value,
    )
    if italian:
        return _normalize_phone(italian.group(1))

    return ""


def _extract_address(text: str) -> str:
    value = " ".join(_text(text).split())

    labelled = re.search(
        r"(?:indirizzo|address)\s*[:\-]\s*"
        r"(.{8,140}?)(?=\s(?:tel|telefono|phone|email|e-mail|p\.iva)\b|$)",
        value,
        flags=re.I,
    )
    if labelled:
        return labelled.group(1).strip(" ,.;")

    street = re.search(
        r"\b(?:Via|Viale|Piazza|Corso|Vicolo|Largo|Piazzale|Strada)\s+"
        r"[A-ZÀ-ÿ0-9][A-ZÀ-ÿ0-9' .\-]{2,70}"
        r"(?:,\s*\d{1,4}[A-Za-z]?)?"
        r"(?:,?\s*\d{5}\s+[A-ZÀ-ÿ' .\-]{2,45})?"
        r"(?:\s+\(?[A-Z]{2}\)?)?",
        value,
        flags=re.I,
    )
    if street:
        candidate = street.group(0).strip(" ,.;")
        if len(candidate) <= 140:
            return candidate

    return ""


def _extract_contact_form_signal(text: str) -> bool:
    normalized = _norm(text)
    strong_patterns = [
        r"completa tutti i campi.*mandare una mail",
        r"modulo di contatto",
        r"contact form",
        r"invia(?:re)? (?:un |il )?messaggio",
        r"scrivici",
        r"contattaci",
        r"mandare una mail",
        r"invia(?:re)? (?:una |un )?email",
    ]
    return any(
        re.search(pattern, normalized, flags=re.I)
        for pattern in strong_patterns
    )


def extract_public_contact_channels(text: str) -> dict:
    return {
        "public_email": _extract_email(text),
        "public_phone": _extract_phone(text),
        "public_address": _extract_address(text),
        "public_contact_form": _extract_contact_form_signal(text),
    }


def score_account_web_result(
    result: dict,
    account: dict,
) -> dict:
    url = _text(result.get("url"))
    title = _text(result.get("title"))
    snippet = _text(result.get("content"))
    domain = _domain(url)

    if not domain or _is_excluded_domain(domain):
        return {
            "website_match_score": 0.0,
            "website_match_reasons": "excluded or missing domain",
        }

    company_name = _text(account.get("company_name"))
    evidence = f"{title} {snippet} {domain}"
    company_ratio = _token_match_ratio(company_name, evidence)

    current_domain = _text(account.get("source_domain")) or _domain(
        _text(account.get("source_url"))
    )
    trusted_source_domain = _trusted_source_domain(account)
    exact_company_phrase = _exact_company_phrase_match(
        company_name,
        evidence,
    )

    if (
        trusted_source_domain
        and domain != trusted_source_domain
        and not exact_company_phrase
    ):
        return {
            "website_match_score": 0.0,
            "website_match_reasons": (
                "cross-domain identity not proven against trusted discovery source"
            ),
        }

    location_terms = [
        _text(account.get("territory_city")),
        _text(account.get("territory_province")),
        _text(account.get("territory_region")),
    ]
    location_match = any(
        term and _norm(term) in _norm(evidence)
        for term in location_terms
    )
    contact_page = any(
        token in _norm(f"{url} {title}")
        for token in ["contatti", "contact", "chi siamo", "about"]
    )

    score = 0.0
    reasons = []

    if company_ratio >= 0.8:
        score += 50
        reasons.append("strong company-name match")
    elif company_ratio >= 0.5:
        score += 35
        reasons.append("partial company-name match")
    elif company_ratio > 0:
        score += 15
        reasons.append("weak company-name match")

    if current_domain and domain == current_domain:
        score += 30
        reasons.append("matches discovery source domain")

        identity_score = 0.0
        try:
            identity_score = float(
                account.get("account_identity_score", 0) or 0
            )
        except Exception:
            identity_score = 0.0

        if identity_score >= 70:
            score += 20
            reasons.append("upstream account identity supports direct-domain match")

    if location_match:
        score += 10
        reasons.append("territory/location evidence")

    if contact_page:
        score += 10
        reasons.append("contact/about page")

    return {
        "website_match_score": min(score, 100.0),
        "website_match_reasons": ", ".join(reasons) or "weak match",
    }


def _search(
    query: str,
    api_key: str,
    max_results: int,
    timeout: int,
) -> list[dict]:
    response = requests.post(
        TAVILY_ENDPOINT,
        json={
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "exclude_domains": ACCOUNT_DISCOVERY_EXCLUDE_DOMAINS
            + [
                "linkedin.com",
                "facebook.com",
                "instagram.com",
                "youtube.com",
                "wikipedia.org",
                "pinterest.com",
            ],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json().get("results", [])


def build_enrichment_queries(account: dict, country: str = "Italy") -> list[str]:
    company_name = _text(account.get("company_name"))
    location = " ".join(
        value
        for value in [
            _text(account.get("territory_city")),
            _text(account.get("territory_province")),
            _text(account.get("territory_region")),
        ]
        if value
    )

    queries = [
        " ".join(
            part
            for part in [
                f'"{company_name}"',
                location,
                country,
                "sito ufficiale contatti",
            ]
            if part
        ),
        " ".join(
            part
            for part in [
                f'"{company_name}"',
                location,
                "telefono email indirizzo medicina estetica",
            ]
            if part
        ),
    ]

    return list(dict.fromkeys(query.strip() for query in queries if query.strip()))


def summarize_enrichment_results(
    account: dict,
    results: list[dict],
    fit_terms: list[str] | None = None,
) -> dict:
    scored = []

    trusted_source_domain = _trusted_source_domain(account)
    source_url = _text(account.get("source_url"))
    if trusted_source_domain and source_url:
        scored.append(
            {
                "title": _text(account.get("source_title"))
                or _text(account.get("company_name")),
                "content": _text(account.get("source_snippet")),
                "url": source_url,
                "website_match_score": 95.0,
                "website_match_reasons": (
                    "trusted discovery source domain preserved"
                ),
            }
        )

    for result in results:
        scored_result = dict(result)
        scored_result.update(score_account_web_result(result, account))
        if scored_result["website_match_score"] > 0:
            scored.append(scored_result)

    scored.sort(
        key=lambda item: item.get("website_match_score", 0),
        reverse=True,
    )

    if not scored:
        return {
            "account_website": "",
            "website_evidence_status": "Needs verification",
            "website_match_score": 0.0,
            "public_phone": "",
            "public_email": "",
            "public_address": "",
            "public_contact_form": False,
            "contact_channel_status": "No public contact channel observed",
            "enrichment_fit_signals": "",
            "account_data_completeness": 0.0,
            "enrichment_status": "Needs Research",
            "enrichment_source_url": "",
            "enrichment_source_urls": "",
            "enrichment_evidence": "",
        }

    best = scored[0]
    best_score = float(best.get("website_match_score", 0) or 0)
    best_domain = _domain(best.get("url", ""))

    if best_score >= 75:
        website_status = "High-confidence direct site"
    elif best_score >= 50:
        website_status = "Probable direct site"
    else:
        website_status = "Needs verification"

    same_domain = [
        result
        for result in scored
        if _domain(result.get("url", "")) == best_domain
    ]
    evidence_results = same_domain[:4] or scored[:4]
    evidence = " ".join(
        f"{_text(item.get('title'))} {_text(item.get('content'))}"
        for item in evidence_results
    )

    contact = extract_public_contact_channels(evidence)

    fit_matches = []
    normalized_evidence = _norm(evidence)
    for term in fit_terms or []:
        if _norm(term) and _norm(term) in normalized_evidence:
            fit_matches.append(term)

    completeness = 0.0
    if best_score >= 50:
        completeness += 35
    if contact["public_phone"]:
        completeness += 20
    if contact["public_email"]:
        completeness += 15
    if contact["public_address"]:
        completeness += 15
    if contact["public_contact_form"]:
        completeness += 10
    if fit_matches:
        completeness += 15

    if contact["public_phone"] and contact["public_email"]:
        contact_status = "Phone and email publicly observed"
    elif contact["public_phone"]:
        contact_status = "Public phone observed"
    elif contact["public_email"]:
        contact_status = "Public email observed"
    elif contact["public_contact_form"]:
        contact_status = "Public website contact form observed"
    else:
        contact_status = "No public contact channel observed"

    if completeness >= 70:
        enrichment_status = "Enriched"
    elif completeness >= 40:
        enrichment_status = "Partially Enriched"
    else:
        enrichment_status = "Needs Research"

    source_urls = list(
        dict.fromkeys(
            _text(item.get("url"))
            for item in evidence_results
            if _text(item.get("url"))
        )
    )

    evidence_snippet = " ".join(
        _text(item.get("content"))
        for item in evidence_results[:2]
        if _text(item.get("content"))
    )[:1600]

    return {
        "account_website": _root_url(best.get("url", "")),
        "website_evidence_status": website_status,
        "website_match_score": best_score,
        "website_match_reasons": _text(best.get("website_match_reasons")),
        "public_phone": contact["public_phone"],
        "public_email": contact["public_email"],
        "public_address": contact["public_address"],
        "public_contact_form": bool(contact["public_contact_form"]),
        "contact_channel_status": contact_status,
        "enrichment_fit_signals": ", ".join(dict.fromkeys(fit_matches)),
        "account_data_completeness": round(completeness, 1),
        "enrichment_status": enrichment_status,
        "enrichment_source_url": _text(best.get("url")),
        "enrichment_source_urls": " | ".join(source_urls),
        "enrichment_evidence": evidence_snippet,
    }


def assess_qualification_readiness(account: dict) -> dict:
    """
    Measure research completeness before commercial qualification.

    This is not an opportunity score or win probability. It only describes
    how much decision-useful account evidence is currently available.
    """

    score = 0.0
    evidence = []

    try:
        identity_score = float(account.get("account_identity_score", 0) or 0)
    except Exception:
        identity_score = 0.0

    if identity_score >= 70:
        score += 20
        evidence.append("account identity")

    location_basis = _text(account.get("territory_location_basis"))
    if location_basis.startswith("Source-observed"):
        score += 20
        evidence.append("source-observed location")
    elif location_basis.startswith("Search-scope inferred"):
        score += 8
        evidence.append("scope-inferred location")

    website_status = _text(account.get("website_evidence_status"))
    if website_status == "High-confidence direct site":
        score += 20
        evidence.append("direct website")
    elif website_status == "Probable direct site":
        score += 12
        evidence.append("probable website")

    if (
        _text(account.get("public_phone"))
        or _text(account.get("public_email"))
        or bool(account.get("public_contact_form", False))
    ):
        score += 15
        evidence.append("public contact channel")

    professional_setting = _text(account.get("professional_setting"))
    if professional_setting and professional_setting != "Unknown setting":
        score += 10
        evidence.append("professional setting")

    if _text(account.get("observed_technology_axes")):
        score += 5
        evidence.append("technology/treatment evidence")

    if bool(account.get("decision_maker_candidate_found", False)):
        score += 5
        evidence.append("decision-maker candidate")

    if bool(account.get("decision_maker_verified", False)):
        score += 5
        evidence.append("high-confidence decision-maker evidence")

    score = min(round(score, 1), 100.0)

    if score >= 70:
        status = "Ready for Qualification"
    elif score >= 45:
        status = "Enrich Before Qualification"
    else:
        status = "Research Required"

    return {
        "qualification_readiness_score": score,
        "qualification_readiness_status": status,
        "qualification_readiness_evidence": ", ".join(evidence),
    }


def enrich_account(
    account: dict,
    api_key: str,
    fit_terms: list[str] | None = None,
    country: str = "Italy",
    max_results_per_query: int = 5,
    timeout: int = 30,
) -> dict:
    if not api_key:
        raise ValueError("A Tavily API key is required for account enrichment.")

    queries = build_enrichment_queries(account, country=country)
    raw_results = []
    seen_urls = set()

    for query in queries:
        for result in _search(
            query=query,
            api_key=api_key,
            max_results=max_results_per_query,
            timeout=timeout,
        ):
            url = _text(result.get("url"))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            enriched_result = dict(result)
            enriched_result["enrichment_query"] = query
            raw_results.append(enriched_result)

    summary = summarize_enrichment_results(
        account=account,
        results=raw_results,
        fit_terms=fit_terms,
    )
    summary["enrichment_queries"] = " | ".join(queries)
    return summary
