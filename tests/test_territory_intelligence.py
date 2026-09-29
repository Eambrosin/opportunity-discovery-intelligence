import unittest

import pandas as pd

from discovery_engine import TargetProfile, screen_candidates, qualification_handoff
from territory_intelligence import (
    apply_territory_intelligence,
    build_territory_search_queries,
    contact_readiness,
    infer_territory_location,
    territory_breakdown,
    territory_gaps,
    technology_landscape,
)
from territory_profiles import NORTH_ITALY_MEDICAL_AESTHETICS, priority_cluster_ids
from vendor_profiles import DELEO_NORTH_ITALY


class TerritoryIntelligenceTests(unittest.TestCase):

    def setUp(self):
        self.territory = NORTH_ITALY_MEDICAL_AESTHETICS
        self.profile = TargetProfile(
            industry="Medical Aesthetics",
            market_profile_id="medical_aesthetics",
            countries=["Italy"],
            regions=["Europe"],
            business_models=[
                "Aesthetic Medicine Clinic",
                "Dermatology Clinic",
                "Aesthetic Center",
            ],
            required_keywords=[
                "medicina estetica",
                "criolipolisi",
                "laser estetico",
                "body contouring",
            ],
            search_archetypes=[
                "clinica medicina estetica",
                "medico estetico studio",
            ],
        )

    def test_priority_territory_queries_include_cluster_location(self):
        cluster_ids = priority_cluster_ids(self.territory)[:4]
        queries = build_territory_search_queries(
            self.profile,
            self.territory,
            cluster_ids,
            max_queries=4,
        )
        joined = " | ".join(queries).lower()
        self.assertEqual(len(queries), 4)
        self.assertTrue(
            any(city in joined for city in ["milano", "monza", "bergamo", "brescia"])
        )

    def test_source_observed_city_gets_high_location_confidence(self):
        row = {
            "company_name": "Example Clinic",
            "source_title": "Clinica di medicina estetica Milano",
            "source_snippet": "Trattamenti di medicina estetica e laser.",
            "source_url": "https://example.com",
            "discovery_query": "medicina estetica Milano Lombardia Italy",
        }
        location = infer_territory_location(row, self.territory)
        self.assertEqual(location["territory_region"], "Lombardia")
        self.assertEqual(location["territory_province"], "Milano")
        self.assertEqual(location["territory_city"], "Milano")
        self.assertEqual(location["territory_location_confidence"], 100.0)

    def test_search_scope_inference_is_explicitly_lower_confidence(self):
        row = {
            "company_name": "Example Clinic",
            "source_title": "Centro medico estetico",
            "source_snippet": "Trattamenti viso e corpo.",
            "source_url": "https://example.com",
            "discovery_query": "clinica medicina estetica Verona Veneto Italy",
        }
        location = infer_territory_location(row, self.territory)
        self.assertEqual(location["territory_region"], "Veneto")
        self.assertEqual(location["territory_province"], "Verona")
        self.assertLess(location["territory_location_confidence"], 75)
        self.assertIn("verify", location["territory_location_basis"].lower())

    def test_deleo_technology_signals_enrich_account_without_product_recommendation(self):
        data = pd.DataFrame(
            [{
                "company_name": "Milano Aesthetic Clinic",
                "country": "Italy",
                "region": "Europe",
                "industry": "Medical Aesthetics",
                "business_model": "Aesthetic Medicine Clinic",
                "company_size": 25,
                "source_title": "Medicina estetica Milano",
                "source_snippet": (
                    "Clinica a Milano con criolipolisi, body contouring, "
                    "laser frazionato e ringiovanimento cutaneo."
                ),
                "source_url": "https://example.com/milano",
                "discovery_query": "clinica medicina estetica Milano Lombardia Italy",
            }]
        )

        ranked = screen_candidates(data, self.profile)
        enriched = apply_territory_intelligence(
            ranked,
            self.territory,
            DELEO_NORTH_ITALY,
        )

        row = enriched.iloc[0]
        self.assertEqual(row["vendor_profile_id"], "deleo_north_italy")
        self.assertIn("Silhouette / Body Contouring", row["observed_technology_axes"])
        self.assertIn("Skin / Regeneration", row["observed_technology_axes"])
        self.assertGreater(row["account_opportunity_score"], 0)
        self.assertNotIn("recommend", row["technology_validation_questions"].lower())

    def test_contact_readiness_can_mark_strong_account_ready_for_field_visit(self):
        contact = {
            "contact_relevance_score": 100,
            "contact_confidence": "High",
            "linkedin_url": "https://www.linkedin.com/in/example",
            "headline": "Medical Director",
            "matched_target_roles": "Medical Director",
        }
        account = {
            "account_opportunity_score": 90,
            "territory_location_confidence": 100,
        }
        readiness = contact_readiness(contact, account)
        self.assertGreaterEqual(readiness["contact_readiness_score"], 85)
        self.assertEqual(readiness["contact_status"], "Ready for Field Visit")

    def test_territory_handoff_preserves_location_and_account_score(self):
        data = pd.DataFrame(
            [{
                "company_name": "Verona Clinic",
                "country": "Italy",
                "region": "Europe",
                "industry": "Medical Aesthetics",
                "business_model": "Aesthetic Medicine Clinic",
                "company_size": 18,
                "source_title": "Medicina estetica Verona",
                "source_snippet": "Clinica medica con trattamenti laser e body contouring.",
                "source_url": "https://example.com/verona",
                "discovery_query": "medicina estetica Verona Veneto Italy",
            }]
        )
        ranked = screen_candidates(data, self.profile)
        enriched = apply_territory_intelligence(
            ranked,
            self.territory,
            DELEO_NORTH_ITALY,
        )
        handoff = qualification_handoff(enriched)

        for column in [
            "territory_profile_id",
            "territory_region",
            "territory_province",
            "account_opportunity_score",
            "territory_status",
            "vendor_profile_id",
        ]:
            self.assertIn(column, handoff.columns)

    def test_breakdown_and_gap_tables_are_generated(self):
        data = pd.DataFrame(
            [{
                "company_name": "Bergamo Clinic",
                "country": "Italy",
                "region": "Europe",
                "industry": "Medical Aesthetics",
                "business_model": "Aesthetic Medicine Clinic",
                "source_title": "Clinica medicina estetica Bergamo",
                "source_snippet": "Medicina estetica e laser.",
                "source_url": "https://example.com/bergamo",
                "discovery_query": "medicina estetica Bergamo Lombardia Italy",
            }]
        )
        ranked = apply_territory_intelligence(
            screen_candidates(data, self.profile),
            self.territory,
            DELEO_NORTH_ITALY,
        )

        by_region = territory_breakdown(ranked, "territory_region")
        gaps = territory_gaps(
            ranked,
            self.territory,
            ["lombardia_bergamo", "veneto_verona"],
        )

        self.assertFalse(by_region.empty)
        self.assertEqual(set(gaps["cluster_id"]), {"lombardia_bergamo", "veneto_verona"})


    def test_gap_table_distinguishes_unsearched_cluster(self):
        ranked = pd.DataFrame(
            [
                {
                    "territory_cluster_id": "lombardia_bergamo",
                    "account_opportunity_score": 85,
                }
            ]
        )
        gaps = territory_gaps(
            ranked,
            self.territory,
            ["lombardia_bergamo", "veneto_verona"],
            searched_cluster_ids=["lombardia_bergamo"],
        )
        verona = gaps[gaps["cluster_id"] == "veneto_verona"].iloc[0]
        self.assertEqual(
            verona["research_gap"],
            "Not searched in current run",
        )

    def test_technology_landscape_uses_not_observed_not_absent(self):
        row = {
            "company_name": "Example Clinic",
            "source_title": "Medicina estetica Milano",
            "source_snippet": "Clinica con criolipolisi e body contouring.",
            "business_model": "Aesthetic Medicine Clinic",
        }
        landscape = technology_landscape(row, DELEO_NORTH_ITALY)
        self.assertFalse(landscape.empty)
        self.assertTrue(
            landscape["evidence_status"]
            .astype(str)
            .str.contains("Not observed|Observed")
            .all()
        )
        self.assertFalse(
            landscape["evidence_status"]
            .astype(str)
            .str.lower()
            .str.contains("absent")
            .any()
        )


if __name__ == "__main__":
    unittest.main()
