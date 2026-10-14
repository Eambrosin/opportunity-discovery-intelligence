from __future__ import annotations

from typing import Iterable


def _norm(value) -> str:
    return " ".join(str(value or "").lower().replace("/", " ").replace("-", " ").split())


def classify_counterparty_role(
    evidence: str,
    *,
    focus: str = "Buyers",
    target_partner_types: Iterable[str] = (),
    commercial_track: str = "",
) -> tuple[str, str]:
    normalized = _norm(evidence)
    track = _norm(commercial_track)

    if any(term in track for term in ["held back", "not end customer", "research result"]):
        return "Research / Non-Target", "Held back from commercial execution"

    execution_terms = [
        "technical service",
        "technical support",
        "service center",
        "maintenance",
        "installation",
        "commissioning",
        "integrator",
        "assistenza tecnica",
        "spare parts",
        "ricambi",
    ]
    observed_execution = [term for term in execution_terms if term in normalized]
    if observed_execution:
        return (
            "Execution / Technical Partner",
            "Observed execution-capability signal: " + ", ".join(observed_execution[:3]),
        )

    route_terms = [
        "distributor",
        "distributore",
        "distribuidor",
        "representative",
        "representante",
        "reseller",
        "dealer",
        "channel partner",
    ]
    observed_route = [term for term in route_terms if term in normalized]
    configured_matches = [
        _norm(term)
        for term in target_partner_types
        if _norm(term) and _norm(term) in normalized
    ]
    if observed_route or configured_matches:
        signals = observed_route + configured_matches
        return (
            "Route-to-Market Partner",
            "Observed partner signal: " + ", ".join(dict.fromkeys(signals[:3])),
        )

    normalized_focus = _norm(focus)
    if "partner" in normalized_focus and "buyer" not in normalized_focus:
        return (
            "Partner Candidate — Type to Validate",
            "Mandate is partner-focused; specific partner role still requires validation",
        )

    return (
        "Buyer / End Customer",
        "No partner-specific evidence observed; buyer role remains a commercial hypothesis",
    )
