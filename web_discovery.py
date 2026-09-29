from __future__ import annotations

from urllib.parse import urlparse

import pandas as pd
import requests


TAVILY_ENDPOINT = "https://api.tavily.com/search"


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return host.removeprefix("www.")


def _company_from_title(title: str, domain: str) -> str:
    if title:
        for separator in [" | ", " — ", " - ", ": "]:
            if separator in title:
                candidate = title.split(separator)[0].strip()
                if 2 <= len(candidate) <= 90:
                    return candidate
        if len(title.strip()) <= 90:
            return title.strip()

    if domain:
        stem = domain.split(".")[0].replace("-", " ").strip()
        return stem.title()

    return "Unknown Company"


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
            company_key = company_name.strip().lower()

            # Avoid exact duplicates while allowing a small number of useful
            # directory/profile results from the same domain in fragmented markets.
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
                }
            )

    return pd.DataFrame(rows)
