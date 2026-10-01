import pandas as pd

from field_sales_intelligence import (
    build_field_sales_intelligence,
    product_fit_hypothesis,
    revenue_execution_capacity,
    revenue_target_scenarios,
)
from vendor_profiles import DELEO_NORTH_ITALY


def test_revenue_target_scenarios_match_one_million_target():
    scenarios = revenue_target_scenarios(DELEO_NORTH_ITALY)
    assert scenarios["annual_target_eur"].unique().tolist() == [1_000_000]
    assert scenarios["average_ticket_eur"].tolist() == [15_000, 25_000, 30_000, 40_000]
    assert scenarios["units_per_year"].tolist() == [67, 40, 34, 25]


def test_revenue_execution_capacity_translates_field_activity_into_required_conversion():
    model = revenue_execution_capacity(
        DELEO_NORTH_ITALY,
        field_days_per_month=18,
        qualified_visits_per_day=6.5,
    )
    assert model["qualified_visits_per_month"].unique().tolist() == [117.0]
    ticket_30k = model[model["average_ticket_eur"] == 30_000].iloc[0]
    assert ticket_30k["units_per_month"] == 2.8
    assert 2.0 < ticket_30k["required_visit_to_sale_conversion_pct"] < 3.0
    assert ticket_30k["visits_per_required_sale"] > 40


def test_product_fit_hypothesis_uses_observed_evidence():
    account = {
        "company_name": "Clinic Example",
        "observed_technology_axes": "Silhouette / Body Contouring",
        "source_snippet": "Clinic offering cryolipolysis and body contouring treatments.",
    }
    result = product_fit_hypothesis(account, DELEO_NORTH_ITALY)
    assert result["product_fit_score"] > 0
    assert result["product_fit_family"] != "Needs discovery"


def test_field_visit_priority_rewards_verified_high_fit_account():
    account = {
        "company_name": "High Fit Clinic",
        "target_account_ready": True,
        "account_opportunity_score": 92,
        "qualification_readiness_score": 88,
        "contact_readiness_score": 90,
        "territory_location_confidence": 100,
        "territory_location_basis": "Source-observed city",
        "territory_scope_conflict": False,
        "territory_status": "High-Priority Territory Account",
        "observed_technology_axes": "Skin / Regeneration",
        "source_snippet": "Fractional laser, HIFU and skin rejuvenation treatments.",
        "qualification_questions": "What is the investment timing?",
    }
    result = build_field_sales_intelligence(account, DELEO_NORTH_ITALY)
    assert result["visit_priority_score"] >= 68
    assert result["visit_priority"] in {"Visit Now", "High Priority Visit"}
    assert result["planning_opportunity_value_eur"] == 27_500
    assert "scenario" in result["planning_value_status"].lower()


def test_field_visit_priority_penalizes_out_of_scope_account():
    account = {
        "company_name": "Out of Scope Clinic",
        "target_account_ready": True,
        "account_opportunity_score": 95,
        "qualification_readiness_score": 90,
        "contact_readiness_score": 90,
        "territory_location_confidence": 100,
        "territory_location_basis": "Source-observed city",
        "territory_scope_conflict": True,
        "territory_status": "Out of Territory",
        "source_snippet": "Medical aesthetic clinic.",
    }
    result = build_field_sales_intelligence(account, DELEO_NORTH_ITALY)
    assert result["visit_priority_score"] < 68
    assert result["visit_priority"] in {"Contact / Prepare First", "Research Before Visit"}
