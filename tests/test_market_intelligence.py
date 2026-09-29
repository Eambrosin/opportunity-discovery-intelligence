import unittest

import pandas as pd

from contact_discovery import _parse_person_title, score_contact_result
from discovery_engine import TargetProfile, build_search_queries, qualification_handoff, screen_candidates
from presets import get_preset
from web_discovery import _account_identity, _company_from_title, consolidate_company_results


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


    def test_company_parser_prefers_brand_over_generic_treatment_page(self):
        name = _company_from_title(
            "Programmi viso | Medical Art",
            "medicalart.it",
        )
        self.assertEqual(name, "Medical Art")

    def test_company_parser_prefers_practitioner_over_generic_service_label(self):
        name = _company_from_title(
            "Chirurgia Plastica e Medicina Estetica | Dott.ssa Alessandra Cecchini",
            "alessandracecchini.it",
        )
        self.assertIn("Alessandra Cecchini", name)

    def test_generic_title_uses_practitioner_name_from_snippet(self):
        name = _company_from_title(
            "Medicina e Chirurgia Estetica e Ricostruttiva",
            "alessandracecchini.it",
            "La Dottoressa Alessandra Cecchini è specializzata in Chirurgia Plastica.",
        )
        self.assertEqual(name, "Alessandra Cecchini")

    def test_generic_title_falls_back_to_distinctive_domain_brand(self):
        name = _company_from_title(
            "Medicina e Chirurgia Estetica e Ricostruttiva",
            "alessandracecchini.it",
        )
        self.assertEqual(name, "Alessandracecchini")

    def test_generic_dermatology_title_falls_back_to_domain_brand(self):
        name = _company_from_title(
            "Dermatologo Venereologico",
            "dottorrossi.it",
        )
        self.assertEqual(name, "Dottorrossi")

    def test_generic_service_label_is_not_direct_account_identity(self):
        identity = _account_identity(
            title="Clinica Medicina Estetica",
            url="https://exampleclinic.it/medicina-estetica",
            company_name="Clinica Medicina Estetica",
            domain="exampleclinic.it",
        )
        self.assertFalse(identity["qualification_ready"])
        self.assertIn("Generic service label", identity["account_identity_status"])

    def test_pdf_cv_is_not_qualification_ready(self):
        identity = _account_identity(
            title="CV VINDIGNI VINCENZO 2024",
            url="https://example.org/cv-vindigni-2024.pdf",
            company_name="Example",
            domain="example.org",
        )
        self.assertFalse(identity["qualification_ready"])
        self.assertLess(identity["account_identity_score"], 60)

    def test_directory_result_is_not_qualification_ready(self):
        identity = _account_identity(
            title="Best Facials near me in Verona",
            url="https://www.fresha.com/lp/en/tt/facials/in/it-verona",
            company_name="Best Facials near me in Verona",
            domain="fresha.com",
        )
        self.assertFalse(identity["qualification_ready"])
        self.assertEqual(
            identity["account_identity_status"],
            "Directory / marketplace result — not a direct account",
        )

    def test_sparse_medical_aesthetics_handoff_does_not_raise(self):
        profile = TargetProfile(
            industry="Medical Aesthetics",
            market_profile_id="medical_aesthetics",
            countries=["Italy"],
            regions=["Europe"],
        )
        ranked = pd.DataFrame(
            [
                {
                    "company_name": "Example Clinic",
                    "country": "",
                    "region": "",
                    "industry": "",
                    "company_size": pd.NA,
                    "market_profile_id": "medical_aesthetics",
                    "qualification_ready": True,
                    "discovery_score": 74.9,
                    "confidence": "High",
                    "source_url": "https://exampleclinic.it",
                    "territory_region": "Veneto",
                    "territory_province": "Verona",
                    "territory_city": "Verona",
                    "account_opportunity_score": 82.0,
                }
            ]
        )
        handoff = qualification_handoff(ranked, profile=profile)
        self.assertEqual(len(handoff), 1)
        self.assertEqual(handoff.iloc[0]["schema_version"], "1.0")
        self.assertEqual(handoff.iloc[0]["country"], "Italy")
        self.assertEqual(handoff.iloc[0]["region"], "EU")
        self.assertEqual(handoff.iloc[0]["industry"], "Medical Aesthetics")
        self.assertEqual(handoff.iloc[0]["company_size_status"], "unknown")

    def test_medical_aesthetics_supplier_is_routed_out_of_target_accounts(self):
        profile = TargetProfile(
            industry="Medical Aesthetics",
            market_profile_id="medical_aesthetics",
            countries=["Italy"],
            business_models=["Aesthetic Medicine Clinic", "Medical Practice"],
            required_keywords=["medicina estetica", "laser estetico"],
        )
        data = pd.DataFrame(
            [{
                "company_name": "Example Laser Technologies",
                "source_title": "Example Laser Technologies",
                "source_snippet": (
                    "Produttore di apparecchiature laser ed elettromedicale "
                    "per medici e cliniche di medicina estetica."
                ),
                "source_url": "https://example-lasers.it",
                "qualification_ready": True,
                "account_identity_status": "Likely organization",
            }]
        )
        ranked = screen_candidates(data, profile)
        self.assertFalse(bool(ranked.iloc[0]["target_account_ready"]))
        self.assertEqual(
            ranked.iloc[0]["commercial_track"],
            "Partner / Vendor Candidate",
        )

    def test_medical_aesthetics_clinic_is_target_account_ready(self):
        profile = TargetProfile(
            industry="Medical Aesthetics",
            market_profile_id="medical_aesthetics",
            countries=["Italy"],
            business_models=["Aesthetic Medicine Clinic", "Medical Practice"],
            required_keywords=["medicina estetica", "laser estetico"],
        )
        data = pd.DataFrame(
            [{
                "company_name": "Example Clinic Milano",
                "source_title": "Example Clinic Milano | Medicina Estetica",
                "source_snippet": (
                    "Clinica di medicina estetica a Milano con medico estetico, "
                    "trattamenti laser e ringiovanimento cutaneo."
                ),
                "source_url": "https://example-clinic.it",
                "qualification_ready": True,
                "account_identity_status": "Likely organization",
            }]
        )
        ranked = screen_candidates(data, profile)
        self.assertTrue(bool(ranked.iloc[0]["target_account_ready"]))
        self.assertEqual(
            ranked.iloc[0]["commercial_track"],
            "Practitioner Target",
        )
        self.assertEqual(
            ranked.iloc[0]["score_breakdown"]["industry_fit"],
            100.0,
        )

    def test_same_domain_pages_are_consolidated_into_one_account(self):
        rows = [
            {
                "company_name": "Medical Art",
                "source_title": "Medical Art",
                "source_snippet": "Medicina estetica a Vicenza.",
                "source_url": "https://www.medicalart.it/",
                "source_domain": "medicalart.it",
                "discovery_query": "medical art vicenza",
                "account_identity_score": 90,
                "qualification_ready": True,
            },
            {
                "company_name": "Laser",
                "source_title": "Laser | Medical Art",
                "source_snippet": "Trattamenti laser estetici.",
                "source_url": "https://www.medicalart.it/laser",
                "source_domain": "medicalart.it",
                "discovery_query": "laser estetico vicenza",
                "account_identity_score": 70,
                "qualification_ready": True,
            },
        ]

        consolidated = consolidate_company_results(rows)

        self.assertEqual(len(consolidated), 1)
        row = consolidated.iloc[0]
        self.assertEqual(row["company_name"], "Medical Art")
        self.assertEqual(row["domain_evidence_count"], 2)
        self.assertIn("medicalart.it/laser", row["supporting_source_urls"])
        self.assertIn("Trattamenti laser estetici", row["source_snippet"])


if __name__ == "__main__":
    unittest.main()
