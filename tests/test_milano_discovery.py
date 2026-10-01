from milano_discovery import (
    allocate_milano_query_budget,
    build_milano_discovery_plan,
)


def test_ten_query_budget_uses_three_pass_strategy():
    allocation = allocate_milano_query_budget(10)
    assert allocation == {
        "Market Core": 6,
        "Technology / Treatment": 2,
        "Geographic Coverage": 2,
    }

    plan = build_milano_discovery_plan(10)
    assert len(plan) == 10
    assert [item.stage for item in plan].count("Market Core") == 6
    assert [item.stage for item in plan].count("Technology / Treatment") == 2
    assert [item.stage for item in plan].count("Geographic Coverage") == 2


def test_eight_query_budget_keeps_all_three_passes():
    allocation = allocate_milano_query_budget(8)
    assert allocation == {
        "Market Core": 5,
        "Technology / Treatment": 2,
        "Geographic Coverage": 1,
    }


def test_core_queries_use_natural_italian_market_terms():
    plan = build_milano_discovery_plan(10)
    queries = [item.query for item in plan]
    assert "medicina estetica Milano" in queries
    assert "medico estetico Milano" in queries
    assert "studio medico estetico Milano" in queries
    assert all("Lombardia Italy sito ufficiale" not in query for query in queries)


def test_treatment_and_geo_queries_are_separate_passes():
    plan = build_milano_discovery_plan(10)
    by_stage = {}
    for item in plan:
        by_stage.setdefault(item.stage, []).append(item.query)

    assert any("criolipolisi" in q.lower() for q in by_stage["Technology / Treatment"])
    assert any("Porta Venezia" in q or "Brera" in q for q in by_stage["Geographic Coverage"])
