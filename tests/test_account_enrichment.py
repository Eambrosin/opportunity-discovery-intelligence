import unittest

from account_enrichment import (
    assess_qualification_readiness,
    build_enrichment_queries,
    extract_public_contact_channels,
    score_account_web_result,
    summarize_enrichment_results,
)


class AccountEnrichmentTests(unittest.TestCase):

    def test_extract_public_contact_channels(self):
        text = (
            "Indirizzo: Via Roma 22, 20121 Milano MI. "
            "Tel: +39 02 1234 5678. Email: info@exampleclinic.it"
        )
        result = extract_public_contact_channels(text)
        self.assertEqual(result["public_email"], "info@exampleclinic.it")
        self.assertIn("+39", result["public_phone"])
        self.assertIn("Via Roma", result["public_address"])

    def test_contact_form_is_recognized_as_public_contact_path(self):
        text = (
            "Grazie! Rispondiamo al più presto. "
            "Completa tutti i campi per mandare una mail."
        )
        result = extract_public_contact_channels(text)
        self.assertTrue(result["public_contact_form"])
        self.assertEqual(result["public_email"], "")
        self.assertEqual(result["public_phone"], "")

    def test_direct_source_domain_scores_strongly(self):
        account = {
            "company_name": "Medical Art",
            "source_domain": "medicalart.it",
            "territory_city": "Vicenza",
            "territory_region": "Veneto",
        }
        result = {
            "title": "Medical Art | Medicina Estetica Vicenza",
            "content": "Contatti Medical Art, Vicenza.",
            "url": "https://www.medicalart.it/contatti",
        }
        scored = score_account_web_result(result, account)
        self.assertGreaterEqual(scored["website_match_score"], 75)

    def test_summarize_enrichment_keeps_public_evidence_separate(self):
        account = {
            "company_name": "Example Clinic",
            "source_domain": "exampleclinic.it",
            "territory_city": "Verona",
            "territory_region": "Veneto",
        }
        results = [
            {
                "title": "Example Clinic | Contatti",
                "content": (
                    "Example Clinic Verona. Tel: +39 045 123 4567. "
                    "Email: info@exampleclinic.it. "
                    "Laser estetico e medicina estetica."
                ),
                "url": "https://www.exampleclinic.it/contatti",
            }
        ]
        summary = summarize_enrichment_results(
            account,
            results,
            fit_terms=["medicina estetica", "laser estetico"],
        )
        self.assertEqual(
            summary["website_evidence_status"],
            "High-confidence direct site",
        )
        self.assertEqual(summary["public_email"], "info@exampleclinic.it")
        self.assertIn("laser estetico", summary["enrichment_fit_signals"])
        self.assertGreaterEqual(summary["account_data_completeness"], 70)

    def test_queries_include_company_and_territory(self):
        account = {
            "company_name": "Example Clinic",
            "territory_city": "Bergamo",
            "territory_province": "Bergamo",
            "territory_region": "Lombardia",
        }
        queries = build_enrichment_queries(account, country="Italy")
        self.assertTrue(any('"Example Clinic"' in query for query in queries))
        self.assertTrue(any("Bergamo" in query for query in queries))

    def test_generic_account_name_does_not_create_strong_cross_domain_match(self):
        account = {
            "company_name": "Clinica Medicina Estetica",
            "source_domain": "realclinic.it",
            "territory_city": "Milano",
        }
        result = {
            "title": "Clinica Medicina Estetica Milano",
            "content": "Medicina estetica e trattamenti viso a Milano.",
            "url": "https://otherclinic.it",
        }
        scored = score_account_web_result(result, account)
        self.assertLess(scored["website_match_score"], 50)


    def test_trusted_discovery_domain_is_not_replaced_by_similar_cross_domain(self):
        account = {
            "company_name": "Brera Studio Medico",
            "source_domain": "brerastudiomedico.it",
            "source_url": "https://www.brerastudiomedico.it/medicina-estetica.php",
            "source_title": "Brera Studio Medico | Medicina estetica",
            "source_snippet": (
                "VIA FATEBENEFRATELLI 4, MILANO Tel.02 65560938 "
                "Medicina estetica Filler acido ialuronico"
            ),
            "account_identity_score": 90,
            "territory_city": "Milano",
            "territory_region": "Lombardia",
        }
        results = [
            {
                "title": "Istituto Clinico Brera | Medicina Estetica",
                "content": "Centro medico a Milano, medicina estetica e chirurgia plastica.",
                "url": "https://istitutoclinicobrera.it",
            }
        ]

        summary = summarize_enrichment_results(
            account,
            results,
            fit_terms=["medicina estetica", "chirurgia plastica"],
        )

        self.assertEqual(
            summary["account_website"],
            "https://www.brerastudiomedico.it",
        )
        self.assertIn(
            "brerastudiomedico.it",
            summary["enrichment_source_url"],
        )
        self.assertIn("65560938", summary["public_phone"])

    def test_unproven_cross_domain_is_rejected_when_source_identity_is_trusted(self):
        account = {
            "company_name": "Brera Studio Medico",
            "source_domain": "brerastudiomedico.it",
            "source_url": "https://www.brerastudiomedico.it/medicina-estetica.php",
            "account_identity_score": 90,
            "territory_city": "Milano",
        }
        result = {
            "title": "Istituto Clinico Brera",
            "content": "Medicina estetica a Milano.",
            "url": "https://istitutoclinicobrera.it",
        }

        scored = score_account_web_result(result, account)
        self.assertEqual(scored["website_match_score"], 0)
        self.assertIn("cross-domain identity", scored["website_match_reasons"])

    def test_qualification_readiness_separates_research_completeness_from_fit(self):
        result = assess_qualification_readiness(
            {
                "account_identity_score": 90,
                "territory_location_basis": "Source-observed city",
                "website_evidence_status": "High-confidence direct site",
                "public_email": "info@exampleclinic.it",
                "professional_setting": "Medical-setting signal observed",
                "observed_technology_axes": "Skin / Regeneration",
                "decision_maker_candidate_found": True,
                "decision_maker_verified": False,
            }
        )
        self.assertEqual(
            result["qualification_readiness_status"],
            "Ready for Qualification",
        )
        self.assertGreaterEqual(
            result["qualification_readiness_score"],
            70,
        )
        self.assertIn(
            "direct website",
            result["qualification_readiness_evidence"],
        )

    def test_contact_form_counts_toward_research_readiness(self):
        result = assess_qualification_readiness(
            {
                "account_identity_score": 70,
                "territory_location_basis": "Source-observed city",
                "website_evidence_status": "High-confidence direct site",
                "public_contact_form": True,
                "professional_setting": "Medical-setting signal observed",
            }
        )
        self.assertEqual(
            result["qualification_readiness_status"],
            "Ready for Qualification",
        )
        self.assertIn(
            "public contact channel",
            result["qualification_readiness_evidence"],
        )

    def test_scope_inference_without_enrichment_requires_more_research(self):
        result = assess_qualification_readiness(
            {
                "account_identity_score": 70,
                "territory_location_basis": "Search-scope inferred; verify location",
                "professional_setting": "Medical-setting signal observed",
            }
        )
        self.assertEqual(
            result["qualification_readiness_status"],
            "Research Required",
        )
        self.assertLess(
            result["qualification_readiness_score"],
            45,
        )


if __name__ == "__main__":
    unittest.main()
