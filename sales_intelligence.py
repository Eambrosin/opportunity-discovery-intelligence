from __future__ import annotations

from typing import Any

import pandas as pd


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none", "<na>", "null"}:
        return ""
    return text


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"true", "1", "yes", "y"}


def _profile_value(profile: Any, key: str, default: Any = "") -> Any:
    if profile is None:
        return default
    if isinstance(profile, dict):
        return profile.get(key, default)
    return getattr(profile, key, default)


def _profile_list(profile: Any, key: str) -> list[str]:
    value = _profile_value(profile, key, [])
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if value is None:
        return []
    try:
        return [str(item).strip() for item in value if str(item).strip()]
    except Exception:
        return []


def _join_unique(items: list[str], limit: int | None = None) -> str:
    values = []
    seen = set()
    for item in items:
        value = _text(item)
        if not value:
            continue
        normalized = value.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        values.append(value)
        if limit is not None and len(values) >= limit:
            break
    return " | ".join(values)


def _location_is_source_observed(account: dict) -> bool:
    return _text(account.get("territory_location_basis")).startswith(
        "Source-observed"
    )


def _has_business_contact(account: dict) -> bool:
    return bool(
        _text(account.get("public_phone"))
        or _text(account.get("public_email"))
    )


def _has_linkedin_contact(account: dict) -> bool:
    return bool(_text(account.get("decision_maker_linkedin")))


def buyer_access_status(account: dict) -> str:
    decision_candidate = _bool(
        account.get("decision_maker_candidate_found", False)
    )
    decision_verified = _bool(
        account.get("decision_maker_verified", False)
    )
    business_contact = _has_business_contact(account)
    linkedin_contact = _has_linkedin_contact(account)

    if decision_verified and (business_contact or linkedin_contact):
        return "Decision maker + contact path observed"
    if decision_candidate and (business_contact or linkedin_contact):
        return "Decision-maker candidate + contact path observed"
    if decision_candidate:
        return "Decision-maker candidate identified"
    if business_contact:
        return "Business contact channel observed"
    return "Buyer access not established"


def evidence_gaps(account: dict, vendor_profile: dict | None = None) -> list[str]:
    gaps: list[str] = []

    identity_score = _number(account.get("account_identity_score"))
    if identity_score < 70:
        gaps.append("account identity")

    if account.get("territory_location_basis") is not None:
        if not _location_is_source_observed(account):
            gaps.append("source-verified location")

    website_status = _text(account.get("website_evidence_status"))
    if website_status not in {
        "High-confidence direct site",
        "Probable direct site",
    }:
        gaps.append("direct account website")

    if not _has_business_contact(account):
        gaps.append("public business contact channel")

    if not _bool(account.get("decision_maker_candidate_found", False)):
        gaps.append("decision-maker candidate")
    elif not _bool(account.get("decision_maker_verified", False)):
        gaps.append("current decision authority")

    company_size = account.get("company_size")
    try:
        company_size_unknown = company_size is None or pd.isna(company_size)
    except Exception:
        company_size_unknown = not bool(_text(company_size))
    if company_size_unknown:
        gaps.append("company size")

    if vendor_profile and not _text(account.get("observed_technology_axes")):
        gaps.append("current treatment / technology portfolio")

    deal_value_status = _text(account.get("deal_value_status"))
    if deal_value_status in {"", "unknown", "unverified"}:
        gaps.append("commercial scope / potential value")

    engagement_status = _text(account.get("engagement_status"))
    if engagement_status in {"", "unknown", "unverified"}:
        gaps.append("timing / active buying context")

    return list(dict.fromkeys(gaps))


def _sales_motion(
    account: dict,
    gaps: list[str],
) -> str:
    identity_score = _number(account.get("account_identity_score"))
    readiness_score = _number(
        account.get("qualification_readiness_score")
    )
    opportunity_score = _number(
        account.get(
            "account_opportunity_score",
            account.get("discovery_score", 0),
        )
    )
    target_ready = account.get("target_account_ready", True)
    if target_ready is not None and not _bool(target_ready):
        return "Research Identity"

    if identity_score < 70:
        return "Research Identity"
    if opportunity_score < 55:
        return "Validate Fit Before Outreach"
    if readiness_score < 45:
        return "Research & Enrich"
    if readiness_score < 70:
        return "Complete Qualification Research"
    if not _bool(account.get("decision_maker_candidate_found", False)):
        return "Find Decision Maker"

    contact_path = (
        _has_business_contact(account)
        or _has_linkedin_contact(account)
    )
    if contact_path:
        return "Ready for Qualification Outreach"
    return "Prepare Qualification Outreach"


def _next_best_action(
    motion: str,
    account: dict,
    gaps: list[str],
    profile: Any,
) -> str:
    target_roles = _profile_list(profile, "target_roles")
    role_hint = ", ".join(target_roles[:3])

    if motion == "Research Identity":
        return (
            "Confirm that this is a direct target account, establish its official "
            "website and verify location before moving it downstream."
        )
    if motion == "Validate Fit Before Outreach":
        return (
            "Review the observed fit evidence and validate business-model relevance "
            "before spending additional contact-discovery or outreach effort."
        )
    if motion == "Research & Enrich":
        priority = ", ".join(gaps[:3]) or "missing account evidence"
        return (
            f"Enrich the account first, prioritizing {priority}; then recalculate "
            "Qualification Readiness."
        )
    if motion == "Complete Qualification Research":
        priority = ", ".join(gaps[:3]) or "remaining evidence gaps"
        return (
            f"Close the remaining qualification gaps ({priority}) before treating "
            "the account as outreach-ready."
        )
    if motion == "Find Decision Maker":
        suffix = f" Focus on roles such as {role_hint}." if role_hint else ""
        return (
            "Identify and verify a likely decision-maker or strong internal entry point."
            + suffix
        )
    if motion == "Prepare Qualification Outreach":
        return (
            "Use the verified account evidence to prepare a concise qualification-first "
            "message, while establishing a reliable contact path."
        )
    return (
        "Open a qualification-first conversation using only observed evidence; "
        "validate current priorities, decision process, timing and commercial scope "
        "before proposing a specific solution."
    )


def _qualification_questions(
    account: dict,
    profile: Any,
    vendor_profile: dict | None,
    gaps: list[str],
) -> list[str]:
    questions: list[str] = []

    if "source-verified location" in gaps:
        questions.append(
            "Can we confirm the operating location and the site responsible for this decision?"
        )

    if "decision-maker candidate" in gaps or "current decision authority" in gaps:
        questions.append(
            "Who owns this commercial decision, and who else participates in evaluation or approval?"
        )

    if "company size" in gaps:
        questions.append(
            "What is the approximate scale of the practice or business relevant to this opportunity?"
        )

    observed_axes = _text(account.get("observed_technology_axes"))
    if vendor_profile:
        if observed_axes:
            questions.append(
                f"Current evidence mentions {observed_axes}. Which technologies/providers are "
                "actually installed today, and where are the priority gaps or upgrade needs?"
            )
        else:
            questions.append(
                "What treatments, technologies and equipment are currently part of the active portfolio?"
            )

        theme_questions = {
            "Current treatment portfolio":
                "Which treatments currently generate the most patient demand and strategic attention?",
            "Installed technology and current provider":
                "Which equipment and providers are currently installed, and how is that relationship performing?",
            "Patient demand and treatment mix":
                "Which patient needs or treatment categories are growing most strongly?",
            "Training and onboarding expectations":
                "What level of clinical or operational training would be required for a new solution?",
            "Service and after-sales expectations":
                "What service, maintenance and after-sales expectations are essential?",
            "Marketing and patient-development support":
                "Would marketing or patient-development support materially affect the evaluation?",
            "Investment timing and decision process":
                "What is the investment timing, budget/approval path and decision process?",
            "Professional/device eligibility where applicable":
                "Are there professional-use or device-eligibility requirements that must be validated for this setting?",
        }
        for theme in vendor_profile.get("discussion_themes", []):
            question = theme_questions.get(_text(theme))
            if question:
                questions.append(question)
    else:
        questions.extend(
            [
                "What is the current solution/provider arrangement and what would justify evaluating an alternative?",
                "What business priority would this initiative need to support to become relevant now?",
                "What is the expected timing and internal decision/approval process?",
            ]
        )

    if "commercial scope / potential value" in gaps:
        questions.append(
            "What would the realistic commercial scope be if the opportunity is qualified?"
        )

    if "timing / active buying context" in gaps:
        questions.append(
            "Is there an active project or timing window, or is this currently an exploratory discussion?"
        )

    return list(dict.fromkeys(questions))[:8]


def _commercial_hypothesis(
    account: dict,
    vendor_profile: dict | None,
) -> str:
    company = _text(account.get("company_name")) or "This account"
    why = _text(account.get("why_relevant"))
    signals = _text(account.get("matched_keywords"))
    axes = _text(account.get("observed_technology_axes"))
    setting = _text(account.get("professional_setting"))

    evidence_parts = []
    if why:
        evidence_parts.append(why)
    if signals:
        evidence_parts.append(f"observed fit signals: {signals}")
    if axes:
        evidence_parts.append(f"observed treatment/technology axes: {axes}")
    if setting:
        evidence_parts.append(f"setting: {setting}")

    if evidence_parts:
        evidence_text = "; ".join(evidence_parts)
        hypothesis = (
            f"{company} appears worth commercial qualification based on {evidence_text}."
        )
    else:
        hypothesis = (
            f"{company} remains a commercial hypothesis that requires additional evidence."
        )

    if vendor_profile:
        hypothesis += (
            f" Relevance to {vendor_profile.get('company', 'the selected commercial program')} "
            "should be validated through the current portfolio, provider relationship, "
            "support expectations and investment process."
        )

    return hypothesis + " No purchase intent is inferred from public evidence."


def _commercial_angle(
    account: dict,
    profile: Any,
    vendor_profile: dict | None,
    gaps: list[str],
) -> str:
    value_proposition = _text(
        _profile_value(profile, "value_proposition", "")
    )
    signals = _text(
        account.get("observed_technology_axes")
        or account.get("enrichment_fit_signals")
        or account.get("matched_keywords")
        or account.get("why_relevant")
    )

    parts = []
    if value_proposition:
        parts.append(f"Lead with the market value proposition: {value_proposition}")
    else:
        parts.append(
            "Lead with a qualification-first discussion rather than a product claim."
        )

    if signals:
        parts.append(
            f"Anchor the opening in observed evidence ({signals}) and ask the account to confirm it."
        )

    if vendor_profile:
        support_themes = [
            _text(item)
            for item in vendor_profile.get("support_themes", [])
            if _text(item)
        ][:3]
        if support_themes:
            parts.append(
                "If relevance is confirmed, explore "
                + ", ".join(support_themes)
                + " as potential differentiators."
            )

    if gaps:
        parts.append(
            "Do not move to a specific solution recommendation until "
            + ", ".join(gaps[:3])
            + " are validated."
        )

    return " ".join(parts)


def _risk_flags(account: dict, gaps: list[str]) -> list[str]:
    flags: list[str] = []

    if _text(account.get("territory_location_basis")).startswith(
        "Search-scope inferred"
    ):
        flags.append("location is inferred from search scope")

    setting = _text(account.get("professional_setting")).lower()
    if "eligibility to validate" in setting:
        flags.append("professional/device eligibility requires validation")

    website_status = _text(account.get("website_evidence_status"))
    if website_status == "Needs verification":
        flags.append("official website is not yet verified")

    if _bool(account.get("decision_maker_candidate_found", False)) and not _bool(
        account.get("decision_maker_verified", False)
    ):
        flags.append("decision-maker authority is not verified")

    if _number(
        account.get(
            "account_opportunity_score",
            account.get("discovery_score", 0),
        )
    ) < 55:
        flags.append("fit is below the current outreach threshold")

    if "timing / active buying context" in gaps:
        flags.append("active buying context has not been established")

    return list(dict.fromkeys(flags))


def build_sales_intelligence(
    account: dict,
    profile: Any = None,
    vendor_profile: dict | None = None,
) -> dict:
    """
    Convert observed account evidence into a deterministic commercial-research plan.

    The output is intentionally not a win probability, buying-intent score or device
    recommendation. It separates evidence quality from the next commercial action.
    """

    gaps = evidence_gaps(account, vendor_profile=vendor_profile)
    motion = _sales_motion(account, gaps)
    questions = _qualification_questions(
        account=account,
        profile=profile,
        vendor_profile=vendor_profile,
        gaps=gaps,
    )
    risks = _risk_flags(account, gaps)

    return {
        "sales_motion": motion,
        "buyer_access_status": buyer_access_status(account),
        "commercial_hypothesis": _commercial_hypothesis(
            account,
            vendor_profile,
        ),
        "commercial_angle": _commercial_angle(
            account,
            profile,
            vendor_profile,
            gaps,
        ),
        "next_best_action": _next_best_action(
            motion,
            account,
            gaps,
            profile,
        ),
        "qualification_questions": _join_unique(questions),
        "sales_evidence_gaps": _join_unique(gaps),
        "commercial_risk_flags": _join_unique(risks),
        "sales_intelligence_basis": (
            "Observed public evidence + deterministic qualification logic; "
            "no purchase intent or win probability inferred."
        ),
    }
