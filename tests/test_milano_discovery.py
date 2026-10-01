import unittest

from milano_discovery import (
    allocate_milano_query_budget,
    build_milano_discovery_plan,
)


class MilanoDiscoveryTests(unittest.TestCase):
    def test_ten_query_budget_uses_three_pass_strategy(self):
        allocation = allocate_milano_query_budget(10)
        self.assertEqual(
            allocation,
            {
                "Market Core": 6,
                "Technology / Treatment": 2,
                "Geographic Coverage": 2,
            },
        )

        plan = build_milano_discovery_plan(10)
        self.assertEqual(len(plan), 10)
        stages = [item.stage for item in plan]
        self.assertEqual(stages.count("Market Core"), 6)
        self.assertEqual(stages.count("Technology / Treatment"), 2)
        self.assertEqual(stages.count("Geographic Coverage"), 2)

    def test_eight_query_budget_keeps_all_three_passes(self):
        allocation = allocate_milano_query_budget(8)
        self.assertEqual(
            allocation,
            {
                "Market Core": 5,
                "Technology / Treatment": 2,
                "Geographic Coverage": 1,
            },
        )

    def test_core_queries_use_natural_italian_market_terms(self):
        plan = build_milano_discovery_plan(10)
        queries = [item.query for item in plan]
        self.assertIn("medicina estetica Milano", queries)
        self.assertIn("medico estetico Milano", queries)
        self.assertIn("studio medico estetico Milano", queries)
        self.assertTrue(
            all("Lombardia Italy sito ufficiale" not in query for query in queries)
        )

    def test_treatment_and_geo_queries_are_separate_passes(self):
        plan = build_milano_discovery_plan(10)
        by_stage = {}
        for item in plan:
            by_stage.setdefault(item.stage, []).append(item.query)

        self.assertTrue(
            any(
                "criolipolisi" in query.lower()
                for query in by_stage["Technology / Treatment"]
            )
        )
        self.assertTrue(
            any(
                "Porta Venezia" in query or "Brera" in query
                for query in by_stage["Geographic Coverage"]
            )
        )


if __name__ == "__main__":
    unittest.main()
