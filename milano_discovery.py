from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MilanoDiscoveryQuery:
    stage: str
    objective: str
    query: str


MARKET_CORE_QUERIES = [
    "medicina estetica Milano",
    "medico estetico Milano",
    "clinica medicina estetica Milano",
    "centro medicina estetica Milano",
    "studio medico estetico Milano",
    "poliambulatorio medicina estetica Milano",
    "chirurgo plastico medicina estetica Milano",
    "dermatologo medicina estetica Milano",
]

TECHNOLOGY_TREATMENT_QUERIES = [
    "criolipolisi Milano medico estetico",
    "HIFU Milano medicina estetica",
    "laser CO2 frazionato Milano medico estetico",
    "laser dermatologico Milano",
    "rimodellamento corpo Milano medicina estetica",
    "ringiovanimento viso Milano medico estetico",
    "radiofrequenza viso Milano medicina estetica",
    "trattamento cellulite Milano medicina estetica",
]

GEOGRAPHIC_COVERAGE_QUERIES = [
    "medicina estetica Porta Venezia Milano",
    "medico estetico Brera Milano",
    "clinica medicina estetica Porta Nuova Milano",
    "medicina estetica CityLife Milano",
    "medico estetico Porta Romana Milano",
    "medicina estetica Navigli Milano",
    "medico estetico Città Studi Milano",
    "medicina estetica Isola Milano",
]

STAGE_OBJECTIVES = {
    "Market Core": "Find clinics, practices and professionals active in aesthetic medicine.",
    "Technology / Treatment": "Surface accounts with public treatment or technology signals relevant to commercial discovery.",
    "Geographic Coverage": "Recover accounts missed by city-wide searches through selected Milano microzones.",
}


def allocate_milano_query_budget(max_queries: int) -> dict[str, int]:
    total_available = (
        len(MARKET_CORE_QUERIES)
        + len(TECHNOLOGY_TREATMENT_QUERIES)
        + len(GEOGRAPHIC_COVERAGE_QUERIES)
    )
    budget = max(1, min(int(max_queries), total_available))

    if budget == 1:
        return {"Market Core": 1, "Technology / Treatment": 0, "Geographic Coverage": 0}
    if budget == 2:
        return {"Market Core": 2, "Technology / Treatment": 0, "Geographic Coverage": 0}

    core = max(1, round(budget * 0.60))
    technology = max(1, round(budget * 0.25))
    geographic = budget - core - technology

    if geographic < 1:
        geographic = 1
        if core > technology and core > 1:
            core -= 1
        elif technology > 1:
            technology -= 1

    while core + technology + geographic > budget:
        if core > 1:
            core -= 1
        elif technology > 1:
            technology -= 1
        else:
            geographic -= 1

    while core + technology + geographic < budget:
        if core < len(MARKET_CORE_QUERIES):
            core += 1
        elif technology < len(TECHNOLOGY_TREATMENT_QUERIES):
            technology += 1
        else:
            geographic += 1

    return {
        "Market Core": min(core, len(MARKET_CORE_QUERIES)),
        "Technology / Treatment": min(technology, len(TECHNOLOGY_TREATMENT_QUERIES)),
        "Geographic Coverage": min(geographic, len(GEOGRAPHIC_COVERAGE_QUERIES)),
    }


def build_milano_discovery_plan(max_queries: int) -> list[MilanoDiscoveryQuery]:
    allocation = allocate_milano_query_budget(max_queries)
    plan: list[MilanoDiscoveryQuery] = []

    stage_sources = [
        ("Market Core", MARKET_CORE_QUERIES),
        ("Technology / Treatment", TECHNOLOGY_TREATMENT_QUERIES),
        ("Geographic Coverage", GEOGRAPHIC_COVERAGE_QUERIES),
    ]

    for stage, queries in stage_sources:
        for query in queries[: allocation[stage]]:
            plan.append(
                MilanoDiscoveryQuery(
                    stage=stage,
                    objective=STAGE_OBJECTIVES[stage],
                    query=query,
                )
            )

    return plan
