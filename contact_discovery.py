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


def _matches(evidence: str, values: list[str]) -> list[str]:
    haystack = _norm(evidence)
    matches = []
    for value in values:
        token = _norm(value)
        if token and token in haystack:
            matches.append(value)
    return matches


def _looks_like_person_account(value: str) -> bool:
    words = [
        token
        for token in re.findall(r"[A-Za-zÀ-ÿ'’.-]+", str(value or ""))
        if token
    ]
    if not 2 <= len(words) <= 4:
        return False

    blocked = {
        "clinic", "clinica", "medical", "medico", "medicina",
        "center", "centre", "centro", "studio", "istituto",
        "group", "gruppo", "aesthetic", "estetica", "dermatologia",
        "surgery", "chirurgia", "laser", "beauty",
    }
    lowered = {word.lower().strip(".") for word in words}
    return not bool(lowered & blocked)


def _name_match_score(person_name: str, account_name: str) -> tuple[int, str]:
    if not _looks_like_person_account(account_name):
        return 0, ""

    person = _norm(person_name)
    account = _norm(account_name)
    if not person or not account:
        return 0, ""

    if person == account:
        return 45, "exact practitioner-name match"

    person_tokens = person.split()
    account_tokens = account.split()
    if not person_tokens or not account_tokens:
        return 0, ""

    if (
        person_tokens[-1] == account_tokens[-1]
        and person_tokens[0] == account_tokens[0]
    ):
        return 40, "strong practitioner-name match"

    if person_tokens[-1] == account_tokens[-1]:
        return 15, "surname-only match"

    return 0, ""


_LOCATION_ALIASES = {
    "milano": {"milano", "milan"},
    "milan": {"milano", "milan"},
    "lombardia": {"lombardia", "lombardy"},
    "lombardy": {"lombardia", "lombardy"},
    "italy": {"italy", "italia"},
    "italia": {"italy", "italia"},
    "roma": {"roma", "rome"},
    "rome": {"roma", "rome"},
    "venezia": {"venezia", "venice"},
    "venice": {"venezia", "venice"},
}


def _location_match(evidence: str, location_context: str) -> list[str]:
    evidence_norm = _norm(evidence)
    matched = []
    for token in _norm(location_context).split():
        if len(token) < 4:
            continue
        aliases = _LOCATION_ALIASES.get(token, {token})
        if any(alias in evidence_norm for alias in aliases):
            matched.append(token)
    return list(dict.fromkeys(matched))


def _professional_role_signal(evidence: str) -> str:
    text = _norm(evidence)
    signals = [
        "chirurgo estetico",
        "chirurgo plastico",
        "plastic surgeon",
        "aesthetic surgeon",
        "medico estetico",
        "aesthetic physician",
        "dermatologo",
        "dermatologist",
        "medical director",
        "direttore sanitario",
        "titolare",
        "owner",
        "founder",
        "clinic manager",
        "practice manager",
    ]
    for signal in signals:
        if signal in text:
            return signal
    return ""


def _company_match(evidence: str, company_name: str) -> bool:
    company = _norm(company_name)
    if not company:
        return False

    evidence_norm = _norm(evidence)
    if company in evidence_norm:
        return True

    meaningful = [
        token
        for token in company.split()
        if len(token) >= 4 and token not in {"clinic", "medical", "center", "centre"}
    ]
    if not meaningful:
        return False

    required = min(2, len(meaningful))
    return sum(token in evidence_norm for token in meaningful) >= required


def _outreach_angle(matched_roles: list[str]) -> str:
    role_text = _norm(" ".join(matched_roles))

    if any(token in role_text for token in ["medical director", "direttore sanitario", "dermatolog", "chirurgo", "physician", "medico"]):
        return "Clinical evidence, treatment fit, training, safety and protocol integration"
    if any(token in role_text for token in ["founder", "titolare", "owner"]):
        return "Business case, differentiation, utilization, patient development and after-sales support"
    if any(token in role_text for token in ["manager", "practice manager", "clinic manager"]):
        return "Operational fit, staff training, service model, utilization and patient journey"
    if any(token in role_text for token in ["estetista", "esthetician", "beautician"]):
        return "Treatment portfolio, training and client experience; validate professional/device eligibility first"
    return "Validate role, current priorities and treatment portfolio before personalized outreach"


def score_contact_result(
    title: str,
    snippet: str,
    company_name: str,
    target_roles: list[str],
    location_context: str = "",
) -> dict:
    evidence = f"{title} {snippet}".strip()
    current_identity_evidence = f"{title} {snippet[:400]}".strip()
    person_name, _ = _parse_person_title(title)

    roles = _matches(evidence, target_roles)
    role_signal = _professional_role_signal(current_identity_evidence)
    location_matches = _location_match(
        current_identity_evidence,
        location_context,
    )
    company = _company_match(evidence, company_name)
    person_account = _looks_like_person_account(company_name)
    name_score, name_reason = _name_match_score(
        person_name,
        company_name,
    )

    reasons = []
    if person_account:
        score = name_score
        if name_reason:
            reasons.append(name_reason)

        if roles:
            score += 25
            reasons.append("target-role match")
        elif role_signal:
            score += 20
            reasons.append("professional-role signal")

        if location_matches:
            score += 20
            reasons.append("location match")
    else:
        score = 45 if company else 0
        if company:
            reasons.append("company match")
        if roles:
            score += 30
            reasons.append("target-role match")
        elif role_signal:
            score += 15
            reasons.append("professional-role signal")
        if location_matches:
            score += 15
            reasons.append("location match")

    score = min(100, score)

    if score >= 80:
        confidence = "High"
    elif score >= 55:
        confidence = "Medium"
    else:
        confidence = "Low"

    if not reasons:
        reasons.append("weak public-profile match")

    outreach_roles = roles or ([role_signal] if role_signal else [])

    return {
        "contact_relevance_score": score,
        "contact_confidence": confidence,
        "matched_target_roles": ", ".join(roles),
        "professional_role_signal": role_signal,
        "location_match_evidence": ", ".join(location_matches),
        "why_contact": ", ".join(reasons),
        "suggested_outreach_angle": _outreach_angle(outreach_roles),
    }


def _search_linkedin_people(
    queries: list[str],
    api_key: str,
    max_results_per_query: int,
    timeout: int,
    search_depth: str = "basic",
    restrict_to_linkedin_domain: bool = True,
) -> list[dict]:
    results = []
    seen_urls = set()

    for query in queries:
        request_payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results_per_query,
            "include_answer": False,
            "include_raw_content": False,
        }
        if restrict_to_linkedin_domain:
            request_payload["include_domains"] = ["linkedin.com"]

        response = requests.post(
            TAVILY_ENDPOINT,
            json=request_payload,
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()

        for result in payload.get("results", []):
            url = str(result.get("url", "")).strip()
            if not url or url in seen_urls or "linkedin.com/in/" not in url.lower():
                continue
            seen_urls.add(url)
            row = dict(result)
            row["search_query"] = query
            results.append(row)

    return results


def _role_queries(prefix: str, target_roles: list[str], country: str) -> list[str]:
    roles = [role.strip() for role in target_roles if role.strip()]
    if not roles:
        return [" ".join(part for part in [prefix, country] if part)]

    queries = []
    for start in range(0, len(roles), 7):
        chunk = roles[start : start + 7]
        role_fragment = " OR ".join(f'"{role}"' for role in chunk)
        queries.append(
            " ".join(
                part
                for part in [prefix, f"({role_fragment})", country]
                if part
            )
        )
    return queries[:2]



def _account_linkedin_queries(
    company_name: str,
    target_roles: list[str],
    geographic_context: str,
) -> list[str]:
    exact = f'"{company_name}"'
    queries = [
        " ".join(
            part
            for part in [f"site:linkedin.com/in {exact}", geographic_context]
            if part
        ),
        " ".join(
            part
            for part in [exact, "LinkedIn", geographic_context]
            if part
        ),
    ]
    queries.extend(
        _role_queries(exact, target_roles, geographic_context)
    )
    return list(
        dict.fromkeys(
            query.strip()
            for query in queries
            if query.strip()
        )
    )[:4]


def discover_linkedin_contacts(
    company_name: str,
    country: str,
    target_roles: list[str],
    api_key: str,
    max_results: int = 8,
    timeout: int = 30,
    location_context: str = "",
) -> pd.DataFrame:
    if not api_key:
        raise ValueError("A Tavily API key is required for LinkedIn contact discovery.")

    geographic_context = " ".join(
        part for part in [location_context, country] if str(part or "").strip()
    ).strip()
    queries = _account_linkedin_queries(
        company_name=company_name,
        target_roles=target_roles,
        geographic_context=geographic_context,
    )
    per_query = max(3, min(6, max_results // max(1, len(queries)) + 2))

    raw_results = _search_linkedin_people(
        queries=queries,
        api_key=api_key,
        max_results_per_query=per_query,
        timeout=timeout,
        search_depth="basic",
        restrict_to_linkedin_domain=True,
    )

    if not raw_results:
        raw_results = _search_linkedin_people(
            queries=queries[:2],
            api_key=api_key,
            max_results_per_query=max(4, per_query),
            timeout=timeout,
            search_depth="basic",
            restrict_to_linkedin_domain=False,
        )

    rows = []
    for result in raw_results:
        url = str(result.get("url", "")).strip()
        title = str(result.get("title", "")).strip()
        snippet = str(result.get("content", "")).strip()
        person_name, headline = _parse_person_title(title)

        scored = score_contact_result(
            title=title,
            snippet=snippet,
            company_name=company_name,
            target_roles=target_roles,
            location_context=location_context,
        )

        rows.append(
            {
                "person_name": person_name,
                "headline": headline,
                "linkedin_url": url,
                "source_snippet": snippet,
                "source_type": _linkedin_kind(url),
                "search_query": result.get("search_query", ""),
                **scored,
            }
        )

    contacts = pd.DataFrame(rows)
    if contacts.empty:
        return contacts

    raw_count = len(contacts)
    contacts = contacts[
        contacts["contact_relevance_score"] >= 55
    ].copy()

    if contacts.empty:
        empty = pd.DataFrame(columns=list(pd.DataFrame(rows).columns))
        empty.attrs["raw_profile_count"] = raw_count
        empty.attrs["held_back_profile_count"] = raw_count
        return empty

    contacts = contacts.sort_values(
        ["contact_relevance_score", "person_name"],
        ascending=[False, True],
    ).head(max_results).reset_index(drop=True)

    contacts["raw_profile_count"] = raw_count
    contacts["held_back_profile_count"] = raw_count - len(contacts)
    return contacts


def discover_linkedin_market_professionals(
    industry: str,
    country: str,
    target_roles: list[str],
    market_terms: list[str],
    api_key: str,
    max_results: int = 12,
    timeout: int = 30,
    locations: list[str] | None = None,
) -> pd.DataFrame:
    if not api_key:
        raise ValueError("A Tavily API key is required for market-professional discovery.")

    context_terms = [term.strip() for term in market_terms if term.strip()]
    context = " ".join([industry] + context_terms[:3]).strip()

    location_values = [item.strip() for item in (locations or []) if item.strip()]
    if not location_values:
        location_values = [country]

    queries = []
    for location in location_values[:4]:
        location_context = " ".join(
            part for part in [location, country] if part and part not in location
        ).strip()
        queries.extend(_role_queries(context, target_roles, location_context))

    queries = list(dict.fromkeys(queries))[:6]
    per_query = max(3, min(6, max_results // max(1, len(queries)) + 2))

    raw_results = _search_linkedin_people(
        queries=queries,
        api_key=api_key,
        max_results_per_query=per_query,
        timeout=timeout,
        search_depth="basic",
        restrict_to_linkedin_domain=True,
    )

    if not raw_results:
        raw_results = _search_linkedin_people(
            queries=queries[:3],
            api_key=api_key,
            max_results_per_query=max(4, per_query),
            timeout=timeout,
            search_depth="basic",
            restrict_to_linkedin_domain=False,
        )

    rows = []
    for result in raw_results:
        url = str(result.get("url", "")).strip()
        title = str(result.get("title", "")).strip()
        snippet = str(result.get("content", "")).strip()
        evidence = f"{title} {snippet}"
        person_name, headline = _parse_person_title(title)

        role_matches = _matches(evidence, target_roles)
        market_matches = _matches(evidence, context_terms)

        score = 25
        if role_matches:
            score += 50
        if market_matches:
            score += min(25, 10 + (5 * len(market_matches)))
        score = min(score, 100)

        if role_matches and market_matches:
            confidence = "High"
        elif role_matches or market_matches:
            confidence = "Medium"
        else:
            confidence = "Low"

        rows.append(
            {
                "person_name": person_name,
                "headline": headline,
                "professional_relevance_score": score,
                "professional_confidence": confidence,
                "matched_target_roles": ", ".join(role_matches),
                "matched_market_signals": ", ".join(market_matches),
                "suggested_outreach_angle": _outreach_angle(role_matches),
                "linkedin_url": url,
                "source_snippet": snippet,
                "search_query": result.get("search_query", ""),
            }
        )

    professionals = pd.DataFrame(rows)
    if professionals.empty:
        return professionals

    return professionals.sort_values(
        ["professional_relevance_score", "person_name"],
        ascending=[False, True],
    ).head(max_results).reset_index(drop=True)
