from __future__ import annotations

import re
from urllib.parse import urlparse

import pandas as pd
import requests


TAVILY_ENDPOINT = "https://api.tavily.com/search"

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
    "yumpu.com",
    "larena.it",
    "sitri.it",
    "infodent.it",
    "skinchannel.it",
    "enpam.it",
    "unipd.it",
    "webmd.com",
    "groupon.it",
    "geoprogress.eu",
    "reumaticitrentini.it",
    "unimib.it",
    "doctolib.it",
    "giornaleitalianodinefrologia.it",
]

CONTENT_TITLE_PATTERNS = [
    r"^cv\b",
    r"^best .* near me",
    r"^best .* in ",
    r"\bnear me\b",
    r"^top \d+",
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
    r"^archivio eventi",
    r"^eventi$",
    r"^dermatology in ",
    r"^dermatologists? in ",
    r"^aesthetic clinics? in ",
    r"^home$",
    r"^download\b",
    r"^trova il\b",
    r"^trova la\b",
    r"^listaxml$",
]

GENERIC_SERVICE_TOKENS = {
    "a", "al", "alla", "con", "di", "del", "della", "e", "ed", "in",
    "clinic", "clinica", "cliniche", "medical", "medico", "medica",
    "centro", "centri", "studio", "istituto", "poliambulatorio", "poliambulatori",
    "medicina", "estetica", "aesthetic", "dermatologia", "dermatologo",
    "venereologia", "venereologico", "chirurgia", "chirurgo", "plastica",
    "plastico", "ricostruttiva", "rigenerativa", "laser", "trattamenti",
    "trattamento", "specialista", "specialisti", "surgery", "plastic",
    "dermatology", "medicine", "regenerative", "reconstructive",
    "milano", "milan", "monza", "bergamo", "brescia", "como", "varese",
    "verona", "vicenza", "padova", "padua", "treviso", "venezia", "venice",
    "trento", "bolzano", "bozen", "roma", "rome", "italia", "italy",
    "lugano", "moritz",
}


PERSON_NAME_STOPWORDS = {
    "la", "le", "il", "lo", "gli",
    "nel", "nella", "nelle", "nei",
    "dal", "dalla", "dalle",
    "sul", "sulla", "sulle",
    "presso", "per",
}


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

    if " " not in stem:
        lower = stem.lower()
        if len(lower) <= 5 and lower.isalpha():
            return lower.upper()

        if lower.endswith("epartners") and len(lower) > len("epartners"):
            prefix = lower[:-len("epartners")]
            return prefix.capitalize() + " e Partners"

        suffixes = [
            ("regenerative", " Regenerative"),
            ("dermatologo", " Dermatologo"),
            ("dermatology", " Dermatology"),
            ("partners", " Partners"),
            ("aesthetics", " Aesthetics"),
            ("aesthetic", " Aesthetic"),
            ("estetica", " Estetica"),
            ("medical", " Medical"),
            ("clinic", " Clinic"),
            ("italia", " Italia"),
            ("beauty", " Beauty"),
            ("care", " Care"),
            ("group", " Group"),
            ("art", " Art"),
        ]
        for suffix, rendered in suffixes:
            if lower.endswith(suffix) and len(lower) > len(suffix):
                prefix = lower[:-len(suffix)].strip()
                if prefix:
                    return prefix.capitalize() + rendered

    return " ".join(part.capitalize() for part in stem.split()) or "Unknown Company"


def _looks_like_generic_service_label(value: str) -> bool:
    tokens = re.findall(
        r"[a-z0-9à-ÿ]+",
        str(value or "").lower(),
    )
    meaningful = [
        token
        for token in tokens
        if len(token) >= 2 and token not in {"dr", "dott", "dottssa"}
    ]
    if not meaningful:
        return True

    non_generic = [
        token
        for token in meaningful
        if token not in GENERIC_SERVICE_TOKENS
    ]

    # A real brand/practitioner usually contributes at least one distinctive
    # token. Pure specialty + treatment + location labels should not become
    # account identities.
    return len(non_generic) == 0


def _looks_like_person_name(value: str) -> bool:
    text = " ".join(str(value or "").strip().split())
    words = re.findall(r"[A-Za-zÀ-ÿ'’.-]+", text)
    if not 2 <= len(words) <= 4:
        return False

    lowered = {word.lower().strip(".") for word in words}

    if lowered and all(token in GENERIC_SERVICE_TOKENS for token in lowered):
        return False

    blocked = {
        "clinic", "clinica", "medical", "medico", "medicina",
        "centro", "studio", "istituto", "chirurgia", "chirurgo",
        "plastica", "plastico", "dermatologia", "dermatologo",
        "venereologia", "venereologico", "estetica", "aesthetic",
        "laser", "beauty", "home", "surgery", "dermatology",
        "specialista", "specialisti", "trattamento", "trattamenti",
    }
    if lowered & blocked:
        return False
    if lowered & PERSON_NAME_STOPWORDS:
        return False

    capitalized = sum(
        1
        for word in words
        if word and (word[0].isupper() or word[0] in "ÀÈÉÌÒÙ")
    )
    return capitalized >= max(2, len(words) - 1)


def _person_name_from_text(value: str) -> str:
    text = " ".join(str(value or "").split())
    honorific = re.search(
        r"\b(?:Dott\.ssa|Dott\.sse|Dott\.|Dottor\.?|Dottore|Dottoressa|Dr\.?|Prof\.?)\s+",
        text,
    )
    if not honorific:
        return ""

    tail = text[honorific.end():]
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
        normalized = token.lower().strip(".")
        if normalized in GENERIC_SERVICE_TOKENS or normalized in PERSON_NAME_STOPWORDS:
            break

        tokens.append(token)
        cursor += match.end()

    if len(tokens) < 2:
        return ""

    return " ".join(tokens)


def _clean_domain_brand(domain: str) -> str:
    brand = _domain_brand(domain)
    compact = re.sub(r"[^a-z0-9à-ÿ]+", "", brand.lower())
    generic_domains = {
        "clinic", "clinica", "medical", "medicinaestetica",
        "centromedico", "centroestetico", "dermatologia",
        "chirurgiaplastica", "aesthetic", "beauty", "home",
    }
    if not compact or compact in generic_domains:
        return ""
    return brand


def _looks_like_content_title(value: str) -> bool:
    text = " ".join(str(value or "").strip().lower().split())
    if not text:
        return True
    return any(re.search(pattern, text, flags=re.I) for pattern in CONTENT_TITLE_PATTERNS)


def _title_parts(title: str) -> list[str]:
    parts = re.split(r"\s+(?:\||—|–|-)\s+|:\s+", str(title or ""))
    return [part.strip() for part in parts if 2 <= len(part.strip()) <= 90]


def _compact_identity(value: str) -> str:
    return re.sub(r"[^a-z0-9à-ÿ]+", "", str(value or "").lower())


def _title_matches_domain_brand(title: str, domain: str) -> bool:
    stem = _compact_identity(domain.split(".")[0] if domain else "")
    title_compact = _compact_identity(title)
    if not stem or not title_compact:
        return False
    return stem in title_compact or title_compact in stem


def _company_from_title(
    title: str,
    domain: str,
    snippet: str = "",
    url: str = "",
) -> str:
    parts = _title_parts(title)

    person_name = _person_name_from_text(
        " ".join([str(title or ""), str(snippet or "")])
    )
    if person_name:
        return person_name

    non_content_parts = [
        part for part in parts
        if not _looks_like_content_title(part)
    ]

    person_like_parts = [
        part
        for part in non_content_parts
        if _looks_like_person_name(part)
    ]
    if person_like_parts:
        return max(person_like_parts, key=lambda value: len(value.split()))

    domain_brand = _clean_domain_brand(domain)
    root_like = _url_depth(url) == 0 if url else False

    # On a homepage, a title that does not resemble the domain brand is often a
    # marketing slogan or service descriptor. Prefer the stable domain identity.
    if (
        root_like
        and domain_brand
        and not any(_title_matches_domain_brand(part, domain) for part in non_content_parts)
    ):
        return domain_brand

    distinctive_parts = [
        part
        for part in non_content_parts
        if not _looks_like_generic_service_label(part)
    ]
    if distinctive_parts:
        brand_aligned = [
            part
            for part in distinctive_parts
            if _title_matches_domain_brand(part, domain)
        ]
        if brand_aligned:
            return max(brand_aligned, key=_name_distinctiveness)
        return max(distinctive_parts, key=_name_distinctiveness)

    if domain_brand:
        return domain_brand

    organization_parts = [
        part
        for part in non_content_parts
        if any(signal in part.lower() for signal in ORGANIZATION_SIGNALS)
    ]
    if organization_parts:
        return organization_parts[0]
    if non_content_parts:
        return non_content_parts[-1] if len(non_content_parts) > 1 else non_content_parts[0]

    return _domain_brand(domain)


def _account_identity(title: str, url: str, company_name: str, domain: str) -> dict:
    title_text = str(title or "").strip()
    url_path = urlparse(str(url or "")).path.lower()

    directory_like = any(
        domain == blocked or domain.endswith("." + blocked)
        for blocked in ACCOUNT_DISCOVERY_EXCLUDE_DOMAINS
    )

    document_like = (
        directory_like
        or url_path.endswith(".pdf")
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
                "/ricerca.php",
                "/search/",
                "/search?",
            ]
        )
    )

    company_text = str(company_name or "").lower()
    org_signal = any(signal in company_text for signal in ORGANIZATION_SIGNALS)
    generic_account_label = (
        bool(company_name)
        and _looks_like_generic_service_label(company_name)
    )

    if directory_like:
        score = 20
        status = "Directory / marketplace result — not a direct account"
    elif document_like and company_name == _domain_brand(domain):
        score = 25
        status = "Content / document — validate account"
    elif document_like:
        score = 45
        status = "Content page — account name inferred"
    elif generic_account_label:
        score = 45
        status = "Generic service label — direct account identity not established"
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


def _url_depth(url: str) -> int:
    path = urlparse(str(url or "")).path.strip("/")
    if not path:
        return 0
    return len([part for part in path.split("/") if part])


def _name_distinctiveness(company_name: str) -> int:
    generic = {
        "clinic",
        "clinica",
        "medical",
        "medico",
        "medica",
        "centro",
        "center",
        "studio",
        "medicina",
        "estetica",
        "aesthetic",
        "dermatologia",
        "chirurgia",
        "italia",
        "italy",
        "milano",
        "milan",
        "verona",
        "vicenza",
        "padova",
        "brescia",
        "bergamo",
        "venezia",
        "trento",
        "bolzano",
        "varese",
        "como",
        "monza",
    }
    tokens = re.findall(
        r"[a-z0-9à-ÿ]+",
        str(company_name or "").lower(),
    )
    return sum(
        1
        for token in tokens
        if len(token) >= 3 and token not in generic
    )


def consolidate_company_results(rows: list[dict]) -> pd.DataFrame:
    """
    Consolidate multiple pages from the same direct domain into one account candidate.

    The discovery engine keeps supporting URLs/snippets as evidence while preventing
    treatment pages, contact pages and homepage variants from becoming separate leads.
    """
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    if "source_domain" not in frame.columns:
        return frame

    consolidated = []

    for _, group in frame.groupby("source_domain", dropna=False, sort=False):
        working = group.copy()
        working["_ready_rank"] = (
            working.get("qualification_ready", False)
            .fillna(False)
            .astype(bool)
            .astype(int)
        )
        working["_identity_rank"] = pd.to_numeric(
            working.get("account_identity_score", 0),
            errors="coerce",
        ).fillna(0)
        working["_url_depth"] = working["source_url"].map(_url_depth)
        working["_name_distinctiveness"] = working["company_name"].map(
            _name_distinctiveness
        )

        working = working.sort_values(
            [
                "_ready_rank",
                "_identity_rank",
                "_url_depth",
                "_name_distinctiveness",
            ],
            ascending=[False, False, True, False],
        )

        base = working.iloc[0].to_dict()

        supporting_urls = list(
            dict.fromkeys(
                str(value).strip()
                for value in group["source_url"].tolist()
                if str(value).strip()
            )
        )
        snippets = list(
            dict.fromkeys(
                str(value).strip()
                for value in group["source_snippet"].tolist()
                if str(value).strip()
            )
        )
        titles = list(
            dict.fromkeys(
                str(value).strip()
                for value in group["source_title"].tolist()
                if str(value).strip()
            )
        )
        queries = list(
            dict.fromkeys(
                str(value).strip()
                for value in group["discovery_query"].tolist()
                if str(value).strip()
            )
        )

        base["source_snippet"] = " | ".join(snippets[:3])[:3500]
        base["supporting_source_urls"] = " | ".join(supporting_urls)
        base["supporting_source_titles"] = " | ".join(titles[:5])
        base["supporting_discovery_queries"] = " | ".join(queries[:5])
        base["domain_evidence_count"] = int(len(group))

        for internal in [
            "_ready_rank",
            "_identity_rank",
            "_url_depth",
            "_name_distinctiveness",
        ]:
            base.pop(internal, None)

        consolidated.append(base)

    return pd.DataFrame(consolidated)


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
                "exclude_domains": sorted(
                    set((exclude_domains or []) + ACCOUNT_DISCOVERY_EXCLUDE_DOMAINS)
                ),
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
            company_name = _company_from_title(
                title,
                domain,
                result.get("content", ""),
                url,
            )
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

    return consolidate_company_results(rows)
