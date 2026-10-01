from __future__ import annotations

from math import ceil
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
    return "" if text.lower() in {"nan", "none", "<na>", "null"} else text


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


def _norm(value: Any) -> str:
    return " ".join(
        _text(value)
        .lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace("’", "'")
        .split()
    )


def _join_unique(items: list[str], limit: int | None = None) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = _text(item)
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
        if limit is not None and len(values) >= limit:
            break
    return " | ".join(values)


def revenue_target_scenarios(vendor_profile: dict | None) -> pd.DataFrame:
    if not vendor_profile:
        return pd.DataFrame()

    target = int(vendor_profile.get("annual_revenue_target_eur", 0) or 0)
    tickets = [
        int(value)
        for value in vendor_profile.get("ticket_scenarios_eur", [])
        if int(value or 0) > 0
    ]
    if target <= 0 or not tickets:
        return pd.DataFrame()

    rows = []
    for ticket in tickets:
        exact_units = target / ticket
        rows.append(
            {
                "average_ticket_eur": ticket,
                "units_per_year": ceil(exact_units),
                "units_per_month": round(exact_units / 12, 1),
                "annual_target_eur": target,
            }
        )
    return pd.DataFrame(rows)


def _evidence_text(account: dict) -> str:
    fields = [
        "company_name",
        "source_title",
        "source_snippet",
        "matched_keywords",
        "why_relevant",
        "enrichment_fit_signals",
        "enrichment_evidence",
        "observed_technology_axes",
        "technology_evidence",
        "professional_setting",
        "business_model",
    ]
    return " ".join(_text(account.get(field)) for field in fields if _text(account.get(field)))


def revenue_execution_capacity(
    vendor_profile: dict | None,
    *,
    field_days_per_month: int,
    qualified_visits_per_day: float,
) -> pd.DataFrame:
    """
    Translate a revenue target into field-capacity requirements.

    This is a planning model, not a sales forecast. It answers: given a chosen
    field rhythm, what visit-to-sale conversion would be mathematically required
    under each average-ticket scenario?
    """
    scenarios = revenue_target_scenarios(vendor_profile)
    if scenarios.empty:
        return pd.DataFrame()

    field_days = max(0, int(field_days_per_month))
    visits_per_day = max(0.0, float(qualified_visits_per_day))
    visits_per_month = field_days * visits_per_day

    result = scenarios.copy()
    result["field_days_per_month"] = field_days
    result["qualified_visits_per_day"] = visits_per_day
    result["qualified_visits_per_month"] = round(visits_per_month, 1)

    if visits_per_month <= 0:
        result["required_visit_to_sale_conversion_pct"] = 0.0
        result["visits_per_required_sale"] = 0.0
        return result

    exact_units_per_month = (
        result["annual_target_eur"]
        / result["average_ticket_eur"]
        / 12
    )
    result["required_visit_to_sale_conversion_pct"] = (
        exact_units_per_month / visits_per_month * 100
    ).round(2)
    result["visits_per_required_sale"] = (
        visits_per_month / exact_units_per_month
    ).round(1)

    return result


HIGH_SPECIFICITY_PRODUCT_SIGNALS = {
    "hifu",
    "criolipolisi",
    "cryolipolysis",
    "laser frazionato",
    "fractional laser",
    "erbium glass",
    "focused ultrasound",
    "ultrasuoni focalizzati",
    "tonificazione muscolare",
    "muscle toning",
    "muscle stimulation",
    "pavimento pelvico",
    "pelvic floor",
    "radiofrequenza corpo",
    "body layering",
}


def product_fit_hypothesis(
    account: dict,
    vendor_profile: dict | None,
) -> dict:
    if not vendor_profile:
        return {
            "product_fit_family": "",
            "product_fit_score": 0.0,
            "product_fit_status": "No vendor program selected",
            "product_fit_basis": "",
            "product_fit_questions": "",
        }

    solutions = vendor_profile.get("solution_families", [])
    if not solutions:
        return {
            "product_fit_family": "",
            "product_fit_score": 0.0,
            "product_fit_status": "No solution map configured",
            "product_fit_basis": "",
            "product_fit_questions": "",
        }

    evidence = _norm(_evidence_text(account))
    observed_axes = {
        _norm(item)
        for item in _text(account.get("observed_technology_axes")).split(",")
        if _norm(item)
    }

    candidates: list[dict] = []
    weak_signals: list[str] = []

    for solution in solutions:
        matched_terms = [
            term
            for term in solution.get("signals", [])
            if _norm(term) and _norm(term) in evidence
        ]
        matched_axes = [
            axis
            for axis in solution.get("technology_axes", [])
            if _norm(axis) in observed_axes or _norm(axis) in evidence
        ]

        specific_single_signal = any(
            _norm(term) in HIGH_SPECIFICITY_PRODUCT_SIGNALS
            for term in matched_terms
        )
        sufficient_product_evidence = bool(
            matched_axes
            or len(matched_terms) >= 2
            or specific_single_signal
        )

        if (matched_terms or matched_axes) and not sufficient_product_evidence:
            weak_signals.extend(matched_terms)
            continue

        evidence_score = min(
            100.0,
            (45.0 if matched_axes else 0.0)
            + (min(len(matched_terms), 4) * 12.0),
        )
        if sufficient_product_evidence:
            candidates.append(
                {
                    "name": solution.get("name", ""),
                    "score": round(evidence_score, 1),
                    "matched_terms": matched_terms,
                    "matched_axes": matched_axes,
                    "questions": solution.get("qualification_questions", []),
                }
            )

    if not candidates:
        weak_signals = list(dict.fromkeys(weak_signals))
        weak_basis = (
            "Weak public signal observed: "
            + ", ".join(weak_signals[:5])
            + ". Insufficient evidence for a product-specific hypothesis."
            if weak_signals
            else "No product-family signal is established from the current public evidence."
        )
        return {
            "product_fit_family": "Needs discovery",
            "product_fit_score": 0.0,
            "product_fit_status": "No product-specific evidence yet",
            "product_fit_basis": weak_basis,
            "product_fit_questions": (
                "Which treatment categories are strategically most important today? | "
                "Which technologies are already installed, and where are the main gaps? | "
                "Which patient needs are growing fastest?"
            ),
        }

    candidates.sort(key=lambda item: (item["score"], len(item["matched_terms"])), reverse=True)
    best = candidates[0]

    basis_parts = []
    if best["matched_axes"]:
        basis_parts.append("observed axes: " + ", ".join(best["matched_axes"]))
    if best["matched_terms"]:
        basis_parts.append("matched signals: " + ", ".join(best["matched_terms"][:5]))

    if best["score"] >= 80:
        status = "Strong commercial-fit hypothesis"
    elif best["score"] >= 60:
        status = "Commercial-fit hypothesis"
    else:
        status = "Early product-fit hypothesis"

    return {
        "product_fit_family": best["name"],
        "product_fit_score": best["score"],
        "product_fit_status": status,
        "product_fit_basis": "; ".join(basis_parts),
        "product_fit_questions": _join_unique(best["questions"], limit=4),
    }


def planning_opportunity_value(
    account: dict,
    vendor_profile: dict | None,
) -> dict:
    if not vendor_profile:
        return {
            "planning_opportunity_value_eur": 0,
            "planning_value_basis": "No vendor planning scenario selected",
            "planning_value_status": "Unavailable",
        }

    explicit_fields = [
        "estimated_deal_value_eur",
        "deal_value_eur",
    ]
    for field in explicit_fields:
        value = _number(account.get(field), 0.0)
        status = _text(account.get("deal_value_status")).lower()
        if value > 0 and status not in {"unknown", "unverified", "not qualified", "not_qualified"}:
            return {
                "planning_opportunity_value_eur": round(value, 2),
                "planning_value_basis": f"Explicit verified account value from {field}",
                "planning_value_status": "Account-specific value",
            }

    planning_ticket = int(vendor_profile.get("default_planning_ticket_eur", 0) or 0)
    ticket_range = vendor_profile.get("ticket_range_eur", [])
    range_text = ""
    if len(ticket_range) >= 2:
        range_text = f"€{int(ticket_range[0]):,}–€{int(ticket_range[1]):,}"

    if planning_ticket <= 0:
        return {
            "planning_opportunity_value_eur": 0,
            "planning_value_basis": "No planning ticket configured",
            "planning_value_status": "Unavailable",
        }

    return {
        "planning_opportunity_value_eur": planning_ticket,
        "planning_value_basis": (
            f"Scenario-only planning ticket ({range_text or 'configured vendor range'}); "
            "not a quote, forecast or account-specific price"
        ),
        "planning_value_status": "Planning scenario",
    }


def _contact_score(account: dict) -> float:
    direct = _number(account.get("contact_readiness_score"), -1)
    if direct >= 0:
        return max(0.0, min(100.0, direct))

    buyer_access = _text(account.get("buyer_access_status")).lower()
    if "decision maker + contact path" in buyer_access:
        return 100.0
    if "candidate + contact path" in buyer_access or "practitioner candidate + public contact" in buyer_access:
        return 80.0
    if "business contact channel" in buyer_access:
        return 60.0
    if "candidate identified" in buyer_access or "likely decision-maker" in buyer_access:
        return 50.0
    return 25.0


def visit_priority(
    account: dict,
    product_fit_score: float,
) -> dict:
    opportunity = _number(
        account.get("account_opportunity_score", account.get("discovery_score", 0))
    )
    readiness = _number(account.get("qualification_readiness_score"), 0)
    location = _number(account.get("territory_location_confidence"), 20)
    contact = _contact_score(account)

    score = (
        opportunity * 0.35
        + readiness * 0.20
        + contact * 0.15
        + location * 0.15
        + max(0.0, min(100.0, product_fit_score)) * 0.15
    )

    penalties: list[str] = []

    if account.get("target_account_ready") is not None and not _bool(
        account.get("target_account_ready")
    ):
        score -= 45
        penalties.append("target-account identity not ready")

    if _bool(account.get("territory_scope_conflict")):
        score -= 45
        penalties.append("outside selected territory")

    territory_status = _text(account.get("territory_status"))
    if territory_status == "Eligibility Validation":
        score -= 12
        penalties.append("professional/device eligibility requires validation")

    if not _text(account.get("territory_location_basis")).startswith("Source-observed"):
        score -= 8
        penalties.append("location not source-verified")

    sales_motion = _text(account.get("sales_motion"))
    if sales_motion == "Find Decision Maker":
        score = min(score, 67.9)
        penalties.append("decision-maker or strong entry point not yet established")
    elif sales_motion in {
        "Research Identity",
        "Validate Fit Before Outreach",
        "Research & Enrich",
    }:
        score = min(score, 51.9)
        penalties.append("commercial research not ready for field allocation")

    score = round(max(0.0, min(100.0, score)), 1)

    if score >= 82:
        label = "Visit Now"
    elif score >= 68:
        label = "High Priority Visit"
    elif score >= 52:
        label = "Contact / Prepare First"
    else:
        label = "Research Before Visit"

    return {
        "visit_priority_score": score,
        "visit_priority": label,
        "visit_priority_basis": (
            "Weighted field-sales readiness from account opportunity, qualification readiness, "
            "buyer access, location evidence and product-fit evidence"
            + (f"; penalties: {', '.join(penalties)}" if penalties else "")
        ),
    }


def _field_objective(account: dict, product: dict, visit: dict) -> str:
    company = _text(account.get("company_name")) or "the account"
    family = _text(product.get("product_fit_family"))
    buyer = _text(account.get("buyer_access_status"))

    if visit["visit_priority"] == "Research Before Visit":
        return (
            f"Do not spend a field slot on {company} yet. Close the main evidence and buyer-access gaps first."
        )
    if visit["visit_priority"] == "Contact / Prepare First":
        return (
            f"Secure a conversation with the relevant decision-maker at {company}, confirm the current "
            "technology/treatment portfolio and convert the account into a qualified field visit."
        )

    if family and family != "Needs discovery":
        return (
            f"Validate whether the observed need behind the {family} hypothesis is commercially relevant, "
            "understand current equipment/provider performance, patient demand, investment timing and decision process."
        )

    if buyer:
        return (
            "Use the visit to understand the clinic's priority treatment categories, patient demand, "
            "installed technology, decision process and investment timing."
        )
    return (
        "Use the visit to establish the decision-maker, current technology portfolio, priority patient needs "
        "and whether there is a commercially relevant problem worth solving."
    )


def _field_questions(
    account: dict,
    product: dict,
) -> list[str]:
    questions: list[str] = []

    raw = _text(account.get("qualification_questions"))
    if raw:
        questions.extend(item.strip() for item in raw.split(" | ") if item.strip())

    product_questions = _text(product.get("product_fit_questions"))
    if product_questions:
        questions.extend(
            item.strip()
            for item in product_questions.split(" | ")
            if item.strip()
        )

    core_questions = [
        "Which treatments currently generate the most patient demand and revenue?",
        "What are patients asking for that the clinic cannot fully address today?",
        "Which technologies are already installed, and what works well or poorly with them?",
        "What would make a new technology commercially compelling for this clinic?",
        "Who evaluates the technology, who approves the investment, and what is the expected timing?",
    ]
    questions.extend(core_questions)
    return list(dict.fromkeys(questions))[:6]


def build_field_sales_intelligence(
    account: dict,
    vendor_profile: dict | None = None,
) -> dict:
    """
    Build deterministic field-sales guidance from current account evidence.

    Product fit is a commercial hypothesis, not a clinical recommendation.
    Planning value is a scenario for territory/revenue modeling, not a quote,
    forecast or inferred willingness to pay.
    """

    product = product_fit_hypothesis(account, vendor_profile)
    value = planning_opportunity_value(account, vendor_profile)
    visit = visit_priority(account, _number(product.get("product_fit_score"), 0))
    questions = _field_questions(account, product)

    if visit["visit_priority"] in {"Visit Now", "High Priority Visit"}:
        next_action = "Plan / confirm field visit"
    elif visit["visit_priority"] == "Contact / Prepare First":
        next_action = "Contact decision-maker and qualify before allocating a field slot"
    else:
        next_action = "Research and enrich before field allocation"

    return {
        **product,
        **value,
        **visit,
        "field_visit_objective": _field_objective(account, product, visit),
        "field_opening_questions": _join_unique(questions),
        "field_next_best_action": next_action,
        "field_sales_basis": (
            "Evidence-aware field-sales planning. Product fit is a hypothesis; planning value "
            "is scenario-only; no purchase intent, clinical suitability or win probability is inferred."
        ),
    }
