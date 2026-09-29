from __future__ import annotations

import re
from urllib.parse import urlparse

import pandas as pd
import requests


TAVILY_ENDPOINT = "https://api.tavily.com/search"

CONTENT_TITLE_PATTERNS = [
    r"^cv\b",
    r"curriculum",
    r"programma congressuale",
    r"programma congresso",
    r"programmi? viso",
    r"offerte? di lavoro",
    r"lavora con noi",
    r"congresso",
    r"convegno",
    r"programma scientifico",
    r"^criolipolisi$",
    r"^medicina estetica$",
    r"^trattamenti?$",
    r"^laser$",
    r"^news$",
    r"^blog$",
]

ORGANIZATION_SIGNALS = [
    "clinic",
    "clinica",
    "studio",
    "centro",
    "medical",
    "medica",
    "medicina",
    "dermatolog",
    "aesthetic",
    "estetica",
    "beauty",
    "institute",
    "istituto",
    "group",
    "gruppo",
    "hospital",
    "poliambulator",
    "spa",
]


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return host.removeprefix("www.")


def _domain_brand(domain: str) -> str:
    if not domain:
        return "Unknown Company"

    stem = domain.split(".")[0]
    stem = re.sub(r"[-_]+", " ", stem).strip()
    return " ".join(part.capitalize() for part in stem.split()) or "Unknown Company"


def _looks_like_content_title(value: str) -> bool:
    text = " ".join(str(value or "").strip().lower().split())
    if not text:
        return True
    return any(re.search(pattern, text, flags=re.I) for pattern in CONTENT_TITLE_PATTERNS)


def _title_parts(title: str) -> list[str]:
    parts = re.split(r"\s+(?:\||—|–|-)\s+|:\s+", str(title or ""))
    return [part.strip() for part in parts if 2 <= len(part.strip()) <= 90]


def _company_from_title(title: str, domain: str) -> str:
    parts = _title_parts(title)

    # Prefer a title segment that looks like an organization rather than
    # a treatment page, congress programme, job page or PDF title.
    organization_parts = [
        part
        for part in parts
        if not _looks_like_content_title(part)
        and any(signal in part.lower() for signal in ORGANIZATION_SIGNALS)
    ]
    if organization_parts:
        return organization_parts[0]

    non_content_parts = [
        part for part in parts
        if not _looks_like_content_title(part)
    ]
    if non_content_parts:
        return non_content_parts[-1] if len(non_content_parts) > 1 else non_content_parts[0]

    return _domain_brand(domain)


def _account_identity(title: str, url: str, company_name: str, domain: str) -> dict:
    title_text = str(title or "").strip()
    url_path = urlparse(str(url or "")).path.lower()

    document_like = (
        url_path.endswith(".pdf")
        or _looks_like_content_title(title_text)
        or any(
            token in url_path
            for token in [
                "/cv/",
                "/curriculum",
                "/congres",
                "/programma",
                "/news/",
                "/blog/",
                "/lavora-con-noi",
                "/jobs",
            ]
        )
    )

    company_text = str(company_name or "").lower()
    org_signal = any(signal in company_text for signal in ORGANIZATION_SIGNALS)

    if document_like and company_name == _domain_brand(domain):
        score = 25
        status = "Content / document — validate account"
    elif document_like:
        score = 45
        status = "Content page — account name inferred"
    elif org_signal:
        score = 90
        status = "Likely organization"
    elif company_name and company_name != "Unknown Company":
        score = 70
        status = "Probable account"
    else:
        score = 35
        status = "Account identity unclear"

    return {
        "account_identity_score": float(score),
        "account_identity_status": status,
        "qualification_ready": bool(score >= 60),
    }


def discover_with_tavily(
    queries: list[str],
    api_key: str,
    max_results_per_query: int = 5,
    timeout: int = 30,
    search_depth: str = "basic",
    exclude_domains: list[str] | None = None,
) -> pd.DataFrame:
    if not api_key:
        raise ValueError("A Tavily API key is required for public-web discovery.")

    rows = []
    seen_urls = set()
    seen_company_keys = set()
    domain_counts = {}

    for query in queries:
        response = requests.post(
            TAVILY_ENDPOINT,
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": search_depth,
                "max_results": max_results_per_query,
                "include_answer": False,
                "include_raw_content": False,
                "exclude_domains": exclude_domains or [],
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()

        for result in payload.get("results", []):
            url = result.get("url", "")
            domain = _domain(url)
            if not domain or not url or url in seen_urls:
                continue

            title = result.get("title", "")
            company_name = _company_from_title(title, domain)
            identity = _account_identity(
                title=title,
                url=url,
                company_name=company_name,
                domain=domain,
            )
            company_key = company_name.strip().lower()

            if company_key and company_key in seen_company_keys:
                continue

            if domain_counts.get(domain, 0) >= 3:
                continue

            seen_urls.add(url)
            if company_key:
                seen_company_keys.add(company_key)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

            rows.append(
                {
                    "company_name": company_name,
                    "country": "",
                    "region": "",
                    "industry": "",
                    "business_model": "",
                    "company_size": pd.NA,
                    "source_title": title,
                    "source_snippet": result.get("content", ""),
                    "source_url": url,
                    "source_domain": domain,
                    "discovery_query": query,
                    **identity,
                }
            )

    return pd.DataFrame(rows)
