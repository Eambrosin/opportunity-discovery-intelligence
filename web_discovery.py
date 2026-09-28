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
) -> pd.DataFrame:
    if not api_key:
        raise ValueError("A Tavily API key is required for public-web discovery.")

    rows = []
    seen_domains = set()

    for query in queries:
        response = requests.post(
            TAVILY_ENDPOINT,
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": max_results_per_query,
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()

        for result in payload.get("results", []):
            url = result.get("url", "")
            domain = _domain(url)
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)

            title = result.get("title", "")
            rows.append(
                {
                    "company_name": _company_from_title(title, domain),
                    "country": "",
                    "region": "",
                    "industry": "",
                    "business_model": "",
                    "company_size": pd.NA,
                    "source_title": title,
                    "source_snippet": result.get("content", ""),
                    "source_url": url,
                    "discovery_query": query,
                }
            )

    return pd.DataFrame(rows)
