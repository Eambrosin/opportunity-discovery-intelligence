import unittest

from account_enrichment import (
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


if __name__ == "__main__":
    unittest.main()
