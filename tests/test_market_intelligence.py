import unittest

import pandas as pd

from contact_discovery import _parse_person_title, score_contact_result
from discovery_engine import TargetProfile, build_search_queries, screen_candidates
from presets import get_preset


class MarketIntelligenceTests(unittest.TestCase):

    def test_medical_aesthetics_preset_contains_local_market_language(self):
        preset = get_preset("Medical Aesthetics — Clinics & Practitioners (Italy)")
        self.assertEqual(preset["industry"], "Medical Aesthetics")
        self.assertIn("Italy", preset["countries"])
        self.assertIn("clinica medicina estetica", preset["search_archetypes"].lower())
        self.assertIn("Direttore Sanitario", preset["target_roles"])

    def test_search_archetypes_drive_queries(self):
        profile = TargetProfile(
            industry="Medical Aesthetics",
            countries=["Italy"],
            business_models=["Aesthetic Medicine Clinic"],
            required_keywords=["criolipolisi"],
            search_archetypes=["clinica medicina estetica"],
        )
        queries = build_search_queries(profile, max_queries=4)
        joined = " | ".join(queries).lower()
        self.assertIn("clinica medicina estetica", joined)
        self.assertIn("italy", joined)

    def test_linkedin_title_parser(self):
        name, headline = _parse_person_title(
            "Giulia Rossi - Medical Director - Example Clinic | LinkedIn"
        )
        self.assertEqual(name, "Giulia Rossi")
        self.assertIn("Medical Director", headline)

    def test_contact_score_rewards_company_and_role_match(self):
        result = score_contact_result(
            title="Giulia Rossi - Medical Director - Example Clinic | LinkedIn",
            snippet="Medical Director at Example Clinic, Milan.",
            company_name="Example Clinic",
            target_roles=["Medical Director", "Clinic Manager"],
        )
        self.assertEqual(result["contact_relevance_score"], 100)
        self.assertEqual(result["contact_confidence"], "High")
        self.assertIn("Medical Director", result["matched_target_roles"])

    def test_contact_score_marks_weak_public_match_low(self):
        result = score_contact_result(
            title="Luca Bianchi - Sales Manager | LinkedIn",
            snippet="Commercial professional in another industry.",
            company_name="Example Clinic",
            target_roles=["Medical Director"],
        )
        self.assertEqual(result["contact_confidence"], "Low")
        self.assertLess(result["contact_relevance_score"], 50)


    def test_medical_aesthetics_esthetician_setting_requires_validation(self):
        profile = TargetProfile(
            industry="Medical Aesthetics",
            countries=["Italy"],
            business_models=["Centro estetico", "Estetista"],
            required_keywords=["criolipolisi"],
        )
        data = pd.DataFrame(
            [{
                "company_name": "Example Beauty Center",
                "source_title": "Centro estetico Example",
                "source_snippet": "Estetista con trattamenti corpo e criolipolisi.",
                "source_url": "https://example.com",
            }]
        )
        ranked = screen_candidates(data, profile)
        self.assertEqual(
            ranked.iloc[0]["professional_setting"],
            "Professional/device eligibility to validate",
        )


if __name__ == "__main__":
    unittest.main()
