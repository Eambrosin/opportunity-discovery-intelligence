from __future__ import annotations

import re
from urllib.parse import urlparse

import pandas as pd
import requests


TAVILY_ENDPOINT = "https://api.tavily.com/search"


def _norm(value: str) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").split())


def _linkedin_kind(url: str) -> str:
    path = urlparse(url).path.lower()
    if "/in/" in path:
        return "Person"
    if "/company/" in path:
        return "Company"
    return "LinkedIn"


def _parse_person_title(title: str) -> tuple[str, str]:
    clean = re.sub(r"\s*\|\s*LinkedIn\s*$", "", str(title or ""), flags=re.I).strip()
    for sep in [" - ", " — ", " | "]:
        if sep in clean:
            first, rest = clean.split(sep, 1)
            return first.strip(), rest.strip()
    return clean, ""


def _role_matches(evidence: str, target_roles: list[str]) -> list[str]:
    haystack = _norm(evidence)
    matches = []
    for role in target_roles:
        token = _norm(role)
        if token and token in haystack:
            matches.append(role)
    return matches


def _company_match(evidence: str, company_name: str) -> bool:
    company = _norm(company_name)
    if not company:
        return False
    evidence_norm = _norm(evidence)
    if company in evidence_norm:
        return True

    meaningful = [
        token for token in company.split()
        if len(token) >= 4 and token not in {"clinic", "medical", "center", "centre"}
    ]
    return bool(meaningful) and sum(token in evidence_norm for token in meaningful) >= min(2, len(meaningful))


def score_contact_result(
    title: str,
    snippet: str,
    company_name: str,
    target_roles: list[str],
) -> dict:
    evidence = f"{title} {snippet}".strip()
    roles = _role_matches(evidence, target_roles)
    company = _company_match(evidence, company_name)

    if roles and company:
        score = 100
        confidence = "High"
    elif roles:
        score = 75
        confidence = "Medium"
    elif company:
        score = 60
        confidence = "Medium"
    else:
        score = 30
        confidence = "Low"

    reasons = []
    if roles:
        reasons.append("target-role match")
    if company:
        reasons.append("company match")
    if not reasons:
        reasons.append("weak public-profile match")

    return {
        "contact_relevance_score": score,
        "contact_confidence": confidence,
        "matched_target_roles": ", ".join(roles),
        "why_contact": ", ".join(reasons),
    }


def discover_linkedin_contacts(
    company_name: str,
    country: str,
    target_roles: list[str],
    api_key: str,
    max_results: int = 8,
    timeout: int = 30,
) -> pd.DataFrame:
    if not api_key:
        raise ValueError("A Tavily API key is required for LinkedIn contact discovery.")

    roles = [role.strip() for role in target_roles if role.strip()]
    role_fragment = " OR ".join(f'"{role}"' for role in roles[:8])
    query = " ".join(
        part for part in [
            f'"{company_name}"',
            f"({role_fragment})" if role_fragment else "",
            country,
        ]
        if part
    )

    response = requests.post(
        TAVILY_ENDPOINT,
        json={
            "api_key": api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_domains": ["linkedin.com/in"],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()

    rows = []
    seen_urls = set()

    for result in payload.get("results", []):
        url = str(result.get("url", "")).strip()
        if not url or url in seen_urls or "linkedin.com/in/" not in url.lower():
            continue
        seen_urls.add(url)

        title = str(result.get("title", "")).strip()
        snippet = str(result.get("content", "")).strip()
        person_name, headline = _parse_person_title(title)

        scored = score_contact_result(
            title=title,
            snippet=snippet,
            company_name=company_name,
            target_roles=roles,
        )

        rows.append(
            {
                "person_name": person_name,
                "headline": headline,
                "linkedin_url": url,
                "source_snippet": snippet,
                "source_type": _linkedin_kind(url),
                "search_query": query,
                **scored,
            }
        )

    contacts = pd.DataFrame(rows)
    if contacts.empty:
        return contacts

    return contacts.sort_values(
        ["contact_relevance_score", "contact_confidence"],
        ascending=[False, True],
    ).reset_index(drop=True)
