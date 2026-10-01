from __future__ import annotations

import re
from urllib.parse import urlparse

import pandas as pd
import requests


TAVILY_ENDPOINT = "https://api.tavily.com/search"

DECISION_AUTHORITY_TERMS = {
    "direttore sanitario",
    "medical director",
    "titolare",
    "owner",
    "founder",
    "clinic owner",
    "practice owner",
    "amministratore",
    "amministratore delegato",
    "managing director",
    "ceo",
}

PERSON_NAME_ROLE_STOPWORDS = {
    "medico",
    "medica",
    "chirurgo",
    "chirurga",
    "specialista",
    "specializzato",
    "specializzata",
    "odontoiatra",
    "dermatologo",
    "dermatologa",
    "direttore",
    "direttrice",
    "sanitario",
    "sanitaria",
    "fisioterapista",
    "anestesista",
    "biologa",
    "biologo",
    "nutrizionista",
    "igienista",
    "assistente",
    "professore",
    "professoressa",
}


def _norm(value: str) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").split())


def _domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _decision_authority_signal(
    matched_roles: list[str],
    role_signal: str = "",
) -> bool:
    evidence = _norm(" ".join(matched_roles + ([role_signal] if role_signal else [])))
    return any(term in evidence for term in DECISION_AUTHORITY_TERMS)


def _extract_honorific_names(text: str) -> list[str]:
    value = " ".join(str(text or "").split())
    if not value:
        return []

    names = []
    pattern = re.compile(
        r"\b(?:Dott\.ssa|Dott\.sse|Dott\.|Dottor\.?|Dottore|Dottoressa|"
        r"Dr\.?|Prof\.?)\s*",
        flags=re.I,
    )

    for honorific in pattern.finditer(value):
        tail = value[honorific.end():]
        tokens = []
        cursor = 0

        while len(tokens) < 4:
            match = re.match(
                r"\s*([A-ZÀ-Ý][A-Za-zÀ-ÿ'’.-]+)",
                tail[cursor:],
            )
            if not match:
                break

            token = match.group(1).strip(" ,.;|-")
            normalized = _norm(token).strip(".")
            if normalized in PERSON_NAME_ROLE_STOPWORDS:
                break

            tokens.append(token)
            cursor += match.end()

        if len(tokens) >= 2:
            names.append(" ".join(tokens))

    return list(dict.fromkeys(names))


def _person_context(text: str, person_name: str, radius: int = 120) -> str:
    value = str(text or "")
    if not value or not person_name:
        return ""

    needle = person_name.lower()

    # Prefer sentence-level attribution so a role belonging to one doctor is not
    # accidentally assigned to another person listed nearby on the same team page.
    sentence_chunks = [
        chunk.strip()
        for chunk in re.split(r"(?<=[.!?;])\s+|[\r\n]+", value)
        if chunk.strip()
    ]
    matched_sentences = [
        chunk
        for chunk in sentence_chunks
        if needle in chunk.lower()
    ]
    if matched_sentences:
        return " ".join(matched_sentences)

    lower = value.lower()
    windows = []
    start = 0
    while True:
        index = lower.find(needle, start)
        if index < 0:
            break
        left = max(0, index - radius)
        right = min(len(value), index + len(person_name) + radius)
        windows.append(value[left:right])
        start = index + len(needle)

    return " ".join(windows)


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
        ("direttore sanitario", "direttore sanitario"),
        ("medical director", "medical director"),
        ("titolare", "titolare"),
        ("owner", "owner"),
        ("founder", "founder"),
        ("chirurgo estetico", "chirurgo estetico"),
        ("chirurgo plastico", "chirurgo plastico"),
        ("plastic surgeon", "plastic surgeon"),
        ("aesthetic surgeon", "aesthetic surgeon"),
        ("specialista in medicina estetica", "medico estetico"),
        ("medico estetico", "medico estetico"),
        ("aesthetic physician", "aesthetic physician"),
        ("specialista in dermatologia", "dermatologo"),
        ("dermatologo", "dermatologo"),
        ("dermatologist", "dermatologist"),
        ("clinic manager", "clinic manager"),
        ("practice manager", "practice manager"),
    ]
    for phrase, canonical in signals:
        if phrase in text:
            return canonical
    return ""


def _company_match_strength(
    evidence: str,
    company_name: str,
) -> tuple[int, str]:
    company = _norm(company_name)
    if not company:
        return 0, ""

    evidence_norm = _norm(evidence)
    if company in evidence_norm:
        return 100, "exact company-name match"

    generic_tokens = {
        "clinic", "clinica", "cliniche",
        "medical", "medico", "medica", "medici",
        "center", "centre", "centro", "centri",
        "studio", "istituto",
        "medicina", "estetica", "aesthetic",
        "dermatologia", "chirurgia",
        "milano", "milan", "italia", "italy",
    }
    meaningful = [
        token
        for token in company.split()
        if len(token) >= 4 and token not in generic_tokens
    ]
    if not meaningful:
        return 0, ""

    matched = [token for token in meaningful if token in evidence_norm]

    if len(meaningful) >= 2:
        ratio = len(matched) / len(meaningful)
        if len(matched) >= 2 and ratio >= 0.67:
            return 80, "distinctive company-token match"

    if len(meaningful) == 1 and matched:
        return 40, "single distinctive company token only"

    return 0, ""


def _company_match(evidence: str, company_name: str) -> bool:
    strength, _ = _company_match_strength(evidence, company_name)
    return strength >= 70


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
    company_strength, company_reason = _company_match_strength(
        evidence,
        company_name,
    )
    person_account = _looks_like_person_account(company_name)
    name_score, name_reason = _name_match_score(
        person_name,
        company_name,
    )

    reasons = []
    if person_account:
        score = name_score
        account_identity_match = name_score >= 40
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
        account_identity_match = company_strength >= 70
        if company_strength >= 100:
            score = 55
        elif company_strength >= 70:
            score = 45
        else:
            score = 0

        if company_reason:
            reasons.append(company_reason)

        if roles:
            score += 35
            reasons.append("target-role match")
        elif role_signal:
            score += 20
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
        "account_identity_match": bool(account_identity_match),
        "decision_authority_signal": _decision_authority_signal(
            roles,
            role_signal,
        ),
        "company_match_strength": int(company_strength if not person_account else 0),
        "company_match_reason": company_reason if not person_account else "",
        "matched_target_roles": ", ".join(roles),
        "professional_role_signal": role_signal,
        "location_match_evidence": ", ".join(location_matches),
        "why_contact": ", ".join(reasons),
        "suggested_outreach_angle": _outreach_angle(outreach_roles),
    }


def _search_official_site(
    queries: list[str],
    domain: str,
    api_key: str,
    max_results_per_query: int,
    timeout: int,
) -> list[dict]:
    results = []
    seen_urls = set()

    for query in queries:
        response = requests.post(
            TAVILY_ENDPOINT,
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results_per_query,
                "include_answer": False,
                "include_raw_content": False,
                "include_domains": [domain],
            },
            timeout=timeout,
        )
        response.raise_for_status()

        for result in response.json().get("results", []):
            url = str(result.get("url", "")).strip()
            if not url or url in seen_urls or _domain(url) != domain:
                continue
            seen_urls.add(url)
            row = dict(result)
            row["search_query"] = query
            results.append(row)

    return results


def _official_site_queries(
    company_name: str,
    domain: str,
) -> list[str]:
    exact = f'"{company_name}"'
    return [
        f'{exact} "direttore sanitario"',
        f'{exact} titolare founder owner "medical director"',
        f'{exact} team medici "medicina estetica"',
        f'{exact} dermatologo "medico estetico" "chirurgo plastico"',
    ]


def discover_official_site_contacts(
    company_name: str,
    account_website: str,
    source_url: str,
    target_roles: list[str],
    api_key: str,
    max_results: int = 8,
    timeout: int = 30,
) -> pd.DataFrame:
    """
    Find named professionals on the already-verified account domain.

    Official-site role evidence is treated as stronger account-identity evidence
    than a search-indexed social-profile snippet. It can identify a decision maker
    even when LinkedIn does not expose a usable profile.
    """
    if not api_key:
        raise ValueError("A Tavily API key is required for official-site contact discovery.")

    domain = _domain(account_website) or _domain(source_url)
    if not domain:
        return pd.DataFrame()

    queries = _official_site_queries(company_name, domain)
    raw_results = _search_official_site(
        queries=queries,
        domain=domain,
        api_key=api_key,
        max_results_per_query=max(3, min(6, max_results)),
        timeout=timeout,
    )

    rows = []
    seen_people = set()

    for result in raw_results:
        title = str(result.get("title", "")).strip()
        snippet = str(result.get("content", "")).strip()
        evidence = f"{title} {snippet}".strip()

        for person_name in _extract_honorific_names(evidence):
            key = _norm(person_name)
            if not key or key in seen_people:
                continue

            context = _person_context(evidence, person_name) or evidence
            roles = _matches(context, target_roles)
            role_signal = _professional_role_signal(context)
            authority = _decision_authority_signal(roles, role_signal)

            if not roles and not role_signal:
                continue

            score = 65
            reasons = ["official account-domain evidence"]
            if roles:
                score += 20
                reasons.append("target-role match")
            elif role_signal:
                score += 10
                reasons.append("professional-role signal")
            if authority:
                score += 15
                reasons.append("explicit decision-authority signal")

            score = min(score, 100)
            confidence = "High" if authority or roles else "Medium"
            outreach_roles = roles or ([role_signal] if role_signal else [])

            rows.append(
                {
                    "person_name": person_name,
                    "headline": ", ".join(roles) or role_signal,
                    "linkedin_url": "",
                    "source_url": str(result.get("url", "")).strip(),
                    "source_snippet": context[:1400],
                    "source_type": "Official site",
                    "search_query": result.get("search_query", ""),
                    "contact_relevance_score": score,
                    "contact_confidence": confidence,
                    "account_identity_match": True,
                    "decision_authority_signal": bool(authority),
                    "company_match_strength": 100,
                    "company_match_reason": "official account domain",
                    "matched_target_roles": ", ".join(roles),
                    "professional_role_signal": role_signal,
                    "location_match_evidence": "",
                    "why_contact": ", ".join(reasons),
                    "suggested_outreach_angle": _outreach_angle(outreach_roles),
                }
            )
            seen_people.add(key)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values(
        [
            "decision_authority_signal",
            "contact_relevance_score",
            "person_name",
        ],
        ascending=[False, False, True],
    ).head(max_results).reset_index(drop=True)


def _merge_contact_sources(
    official_contacts: pd.DataFrame,
    linkedin_contacts: pd.DataFrame,
    max_results: int,
) -> pd.DataFrame:
    if official_contacts.empty and linkedin_contacts.empty:
        return pd.DataFrame()
    if official_contacts.empty:
        return linkedin_contacts.copy()
    if linkedin_contacts.empty:
        result = official_contacts.copy()
        result["raw_profile_count"] = 0
        result["held_back_profile_count"] = 0
        return result

    linkedin_by_name = {
        _norm(row.get("person_name")): row
        for _, row in linkedin_contacts.iterrows()
        if _norm(row.get("person_name"))
    }

    merged_rows = []
    used_linkedin_names = set()

    for _, official in official_contacts.iterrows():
        row = official.to_dict()
        key = _norm(row.get("person_name"))
        linkedin = linkedin_by_name.get(key)

        if linkedin is not None:
            used_linkedin_names.add(key)
            row["linkedin_url"] = str(linkedin.get("linkedin_url", "") or "")
            if not row.get("headline"):
                row["headline"] = str(linkedin.get("headline", "") or "")
            row["source_type"] = "Official site + LinkedIn"
            row["contact_relevance_score"] = max(
                float(row.get("contact_relevance_score", 0) or 0),
                float(linkedin.get("contact_relevance_score", 0) or 0),
            )
            row["contact_confidence"] = "High"
            row["why_contact"] = (
                str(row.get("why_contact", "")).rstrip(", ")
                + ", corroborated by LinkedIn profile evidence"
            )

        merged_rows.append(row)

    for _, linkedin in linkedin_contacts.iterrows():
        key = _norm(linkedin.get("person_name"))
        if key in used_linkedin_names:
            continue
        merged_rows.append(linkedin.to_dict())

    result = pd.DataFrame(merged_rows)
    if result.empty:
        return result

    if "decision_authority_signal" not in result.columns:
        result["decision_authority_signal"] = False
    result["decision_authority_signal"] = (
        result["decision_authority_signal"].fillna(False).astype(bool)
    )

    result = result.sort_values(
        [
            "decision_authority_signal",
            "contact_relevance_score",
            "person_name",
        ],
        ascending=[False, False, True],
    ).head(max_results).reset_index(drop=True)

    result["raw_profile_count"] = int(
        linkedin_contacts.get(
            "raw_profile_count",
            pd.Series([len(linkedin_contacts)]),
        ).iloc[0]
    )
    result["held_back_profile_count"] = int(
        linkedin_contacts.get(
            "held_back_profile_count",
            pd.Series([0]),
        ).iloc[0]
    )
    return result


def discover_account_contacts(
    company_name: str,
    account_website: str,
    source_url: str,
    country: str,
    target_roles: list[str],
    api_key: str,
    max_results: int = 8,
    timeout: int = 30,
    location_context: str = "",
) -> pd.DataFrame:
    official_contacts = discover_official_site_contacts(
        company_name=company_name,
        account_website=account_website,
        source_url=source_url,
        target_roles=target_roles,
        api_key=api_key,
        max_results=max_results,
        timeout=timeout,
    )

    linkedin_contacts = discover_linkedin_contacts(
        company_name=company_name,
        country=country,
        target_roles=target_roles,
        api_key=api_key,
        max_results=max_results,
        timeout=timeout,
        location_context=location_context,
    )

    return _merge_contact_sources(
        official_contacts,
        linkedin_contacts,
        max_results=max_results,
    )


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
        (contacts["contact_relevance_score"] >= 55)
        & contacts["account_identity_match"].fillna(False).astype(bool)
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
