import unittest

from sales_intelligence import (
    build_sales_intelligence,
    buyer_access_status,
    evidence_gaps,
)
from vendor_profiles import DELEO_NORTH_ITALY


class SalesIntelligenceTests(unittest.TestCase):

    def test_low_readiness_prioritizes_research_and_enrichment(self):
        result = build_sales_intelligence(
            {
                "company_name": "Example Clinic",
                "target_account_ready": True,
                "account_identity_score": 85,
                "discovery_score": 74,
                "qualification_readiness_score": 35,
                "territory_location_basis": "Search-scope inferred; verify location",
            }
        )
        self.assertEqual(result["sales_motion"], "Research & Enrich")
        self.assertIn("source-verified location", result["sales_evidence_gaps"])
        self.assertIn("Enrich the account first", result["next_best_action"])

    def test_ready_account_without_decision_maker_moves_to_contact_research(self):
        result = build_sales_intelligence(
            {
                "company_name": "Example Clinic",
                "target_account_ready": True,
                "account_identity_score": 90,
                "discovery_score": 78,
                "qualification_readiness_score": 78,
                "website_evidence_status": "High-confidence direct site",
                "public_email": "info@exampleclinic.it",
                "territory_location_basis": "Source-observed city",
                "decision_maker_candidate_found": False,
            },
            profile={
                "target_roles": ["Medical Director", "Owner"],
                "value_proposition": "Advanced technology and commercial support.",
            },
        )
        self.assertEqual(result["sales_motion"], "Find Decision Maker")
        self.assertIn("Medical Director", result["next_best_action"])

    def test_decision_maker_and_contact_path_support_qualification_outreach(self):
        account = {
            "company_name": "Example Clinic",
            "target_account_ready": True,
            "account_identity_score": 95,
            "account_opportunity_score": 81,
            "qualification_readiness_score": 85,
            "website_evidence_status": "High-confidence direct site",
            "territory_location_basis": "Source-observed city",
            "decision_maker_candidate_found": True,
            "decision_maker_verified": True,
            "decision_maker_linkedin": "https://www.linkedin.com/in/example",
        }
        result = build_sales_intelligence(account)
        self.assertEqual(
            result["sales_motion"],
            "Ready for Qualification Outreach",
        )
        self.assertEqual(
            buyer_access_status(account),
            "Decision maker + contact path observed",
        )

    def test_vendor_context_creates_questions_without_claiming_purchase_intent(self):
        result = build_sales_intelligence(
            {
                "company_name": "Medical Art",
                "target_account_ready": True,
                "account_identity_score": 90,
                "account_opportunity_score": 79,
                "qualification_readiness_score": 72,
                "territory_location_basis": "Source-observed city",
                "website_evidence_status": "High-confidence direct site",
                "observed_technology_axes": "Skin / Regeneration",
                "professional_setting": "Medical-setting signal observed",
                "decision_maker_candidate_found": False,
            },
            profile={
                "value_proposition": (
                    "Advanced aesthetic-medical technology supported by training and service."
                ),
                "target_roles": ["Medical Director"],
            },
            vendor_profile=DELEO_NORTH_ITALY,
        )
        self.assertIn(
            "installed",
            result["qualification_questions"].lower(),
        )
        self.assertIn(
            "No purchase intent is inferred",
            result["commercial_hypothesis"],
        )
        self.assertNotIn("buy now", result["commercial_angle"].lower())

    def test_evidence_gaps_keep_commercial_unknowns_explicit(self):
        gaps = evidence_gaps(
            {
                "account_identity_score": 90,
                "website_evidence_status": "High-confidence direct site",
                "public_phone": "+39 02 000000",
                "decision_maker_candidate_found": True,
                "decision_maker_verified": False,
            }
        )
        self.assertIn("current decision authority", gaps)
        self.assertIn("commercial scope / potential value", gaps)
        self.assertIn("timing / active buying context", gaps)


if __name__ == "__main__":
    unittest.main()
