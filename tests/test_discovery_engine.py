import unittest

import pandas as pd

from discovery_engine import (
    TargetProfile,
    build_search_queries,
    qualification_handoff,
    screen_candidates,
)


class OpportunityDiscoveryTests(unittest.TestCase):

    def setUp(self):
        self.profile = TargetProfile(
            industry="Renewable Energy",
            countries=["Italy", "France"],
            regions=["Europe"],
            business_models=["Distributor", "Wholesaler"],
            required_keywords=["solar", "storage"],
            excluded_keywords=["residential installer"],
            min_company_size=20,
            max_company_size=500,
        )

        self.data = pd.DataFrame(
            [
                {
                    "company_name": "Strong Distributor",
                    "country": "Italy",
                    "region": "Europe",
                    "industry": "Renewable Energy",
                    "business_model": "Distributor",
                    "company_size": 150,
                    "source_title": "Strong Distributor Solar",
                    "source_snippet": "B2B solar distributor with commercial battery storage products.",
                    "source_url": "https://example.com/strong",
                },
                {
                    "company_name": "Residential Installer",
                    "country": "Italy",
                    "region": "Europe",
                    "industry": "Renewable Energy",
                    "business_model": "Installer",
                    "company_size": 30,
                    "source_title": "Residential Installer",
                    "source_snippet": "Residential installer for homeowners and rooftop solar.",
                    "source_url": "https://example.com/installer",
                },
                {
                    "company_name": "Unrelated Company",
                    "country": "Canada",
                    "region": "North America",
                    "industry": "Hospitality",
                    "business_model": "Hotel",
                    "company_size": 800,
                    "source_title": "Unrelated Company",
                    "source_snippet": "Hospitality company operating hotels.",
                    "source_url": "https://example.com/unrelated",
                },
            ]
        )

    def test_search_queries_include_market_and_industry(self):
        queries = build_search_queries(self.profile)
        self.assertTrue(any("Renewable Energy" in query for query in queries))
        self.assertTrue(any("Italy" in query for query in queries))

    def test_strong_candidate_ranks_first(self):
        ranked = screen_candidates(self.data, self.profile)
        self.assertEqual(ranked.iloc[0]["company_name"], "Strong Distributor")
        self.assertGreaterEqual(ranked.iloc[0]["discovery_score"], 80)

    def test_excluded_keyword_caps_score_and_action(self):
        ranked = screen_candidates(self.data, self.profile)
        row = ranked[ranked["company_name"] == "Residential Installer"].iloc[0]
        self.assertEqual(row["recommended_action"], "Exclude")
        self.assertLessEqual(row["discovery_score"], 25)

    def test_unrelated_candidate_scores_below_strong_candidate(self):
        ranked = screen_candidates(self.data, self.profile)
        strong = ranked[ranked["company_name"] == "Strong Distributor"].iloc[0]
        unrelated = ranked[ranked["company_name"] == "Unrelated Company"].iloc[0]
        self.assertGreater(strong["discovery_score"], unrelated["discovery_score"])

    def test_handoff_preserves_decision_maker_authority_evidence(self):
        ranked = pd.DataFrame(
            [
                {
                    "company_name": "Brera Studio Medico",
                    "country": "Italy",
                    "region": "Europe",
                    "industry": "Medical Aesthetics",
                    "qualification_ready": True,
                    "decision_maker_name": "Fabrizio Cecchini",
                    "decision_maker_headline": "Direttore Sanitario",
                    "decision_maker_source_url": "https://www.brerastudiomedico.it/team",
                    "decision_maker_source_type": "Official site",
                    "decision_maker_authority_signal": True,
                    "decision_maker_verified": True,
                    "discovery_score": 70,
                    "confidence": "High",
                    "source_url": "https://www.brerastudiomedico.it",
                    "account_identity_score": 90,
                    "account_identity_status": "Verified organization",
                }
            ]
        )

        handoff = qualification_handoff(ranked)
        row = handoff.iloc[0]

        self.assertEqual(row["decision_maker_name"], "Fabrizio Cecchini")
        self.assertEqual(row["decision_maker_headline"], "Direttore Sanitario")
        self.assertEqual(row["decision_maker_source_type"], "Official site")
        self.assertTrue(bool(row["decision_maker_authority_signal"]))

    def test_handoff_is_qualification_compatible_template(self):
        ranked = screen_candidates(self.data, self.profile)
        handoff = qualification_handoff(ranked)
        required = {
            "company_name",
            "country",
            "region",
            "industry",
            "company_size",
            "estimated_deal_value_usd",
            "engagement_signal",
            "discovery_score",
        }
        self.assertTrue(required.issubset(set(handoff.columns)))
        self.assertTrue((handoff["requires_manual_qualification"] == True).all())


if __name__ == "__main__":
    unittest.main()
