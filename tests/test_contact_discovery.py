import unittest
from unittest.mock import Mock, patch

from contact_discovery import (
    _account_linkedin_queries,
    _search_linkedin_people,
    discover_linkedin_contacts,
    score_contact_result,
)


class ContactDiscoveryTests(unittest.TestCase):

    def test_account_queries_start_with_direct_identity_search(self):
        queries = _account_linkedin_queries(
            company_name="Alessandra Cecchini",
            target_roles=["Titolare", "Medical Director"],
            geographic_context="Milano Lombardia Italy",
        )
        self.assertGreaterEqual(len(queries), 2)
        self.assertIn(
            'site:linkedin.com/in "Alessandra Cecchini"',
            queries[0],
        )
        self.assertIn(
            '"Alessandra Cecchini" LinkedIn',
            queries[1],
        )

    @patch("contact_discovery.requests.post")
    def test_tavily_domain_filter_uses_hostname_not_path(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"results": []}
        post.return_value = response

        _search_linkedin_people(
            queries=['"Example Person" LinkedIn'],
            api_key="test-key",
            max_results_per_query=3,
            timeout=5,
            restrict_to_linkedin_domain=True,
        )

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["include_domains"], ["linkedin.com"])
        self.assertNotIn("linkedin.com/in", payload["include_domains"])

    @patch("contact_discovery.requests.post")
    def test_unrestricted_fallback_still_accepts_only_person_profiles(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "results": [
                {
                    "url": "https://it.linkedin.com/in/alessandra-cecchini",
                    "title": "Alessandra Cecchini | LinkedIn",
                    "content": "Milano, Lombardia, Italia",
                },
                {
                    "url": "https://www.linkedin.com/company/example",
                    "title": "Example | LinkedIn",
                    "content": "",
                },
                {
                    "url": "https://example.com/profile",
                    "title": "Example",
                    "content": "",
                },
            ]
        }
        post.return_value = response

        results = _search_linkedin_people(
            queries=['"Alessandra Cecchini" LinkedIn'],
            api_key="test-key",
            max_results_per_query=5,
            timeout=5,
            restrict_to_linkedin_domain=False,
        )

        self.assertEqual(len(results), 1)
        self.assertIn(
            "linkedin.com/in/",
            results[0]["url"].lower(),
        )


    def test_correct_practitioner_profile_outranks_scientist_homonym(self):
        correct = score_contact_result(
            title="Alessandra Cecchini - Chirurgo estetico - Loconlus ONLUS",
            snippet=(
                "Alessandra Cecchini Chirurgo estetico Milan, Lombardy, Italy. "
                "Lavoro per ricreare l'armonia tra l'immagine e l'essenza di una persona."
            ),
            company_name="Alessandra Cecchini",
            target_roles=["Titolare", "Medical Director", "Chirurgo Plastico"],
            location_context="Milano Lombardia Italy",
        )
        scientist = score_contact_result(
            title=(
                "Alessandra (Lale) Cecchini - Staff Scientist | Team Builder"
            ),
            snippet=(
                "San Diego, California, United States. "
                "Stem cell, aging, molecular and cellular biology."
            ),
            company_name="Alessandra Cecchini",
            target_roles=["Titolare", "Medical Director", "Chirurgo Plastico"],
            location_context="Milano Lombardia Italy",
        )

        self.assertGreaterEqual(correct["contact_relevance_score"], 80)
        self.assertEqual(correct["contact_confidence"], "High")
        self.assertIn("chirurgo estetico", correct["professional_role_signal"])
        self.assertTrue(correct["location_match_evidence"])
        self.assertLess(scientist["contact_relevance_score"], 55)


    def test_org_contact_requires_real_account_identity(self):
        unrelated = score_contact_result(
            title="Daniela Sapienza - Receptionist - Centro Medico Specialistico Milano",
            snippet="Novate Milanese, Lombardia, Italia.",
            company_name="Brera Studio Medico",
            target_roles=["Titolare", "Medical Director", "Direttore Sanitario"],
            location_context="Milano Lombardia",
        )
        self.assertFalse(unrelated["account_identity_match"])
        self.assertLess(unrelated["contact_relevance_score"], 55)

    def test_exact_account_receptionist_is_entry_point_not_decision_maker(self):
        receptionist = score_contact_result(
            title="Maria Rossi - Receptionist | Brera Studio Medico",
            snippet="Brera Studio Medico, Milano, Lombardia.",
            company_name="Brera Studio Medico",
            target_roles=["Titolare", "Medical Director", "Direttore Sanitario"],
            location_context="Milano Lombardia",
        )
        self.assertTrue(receptionist["account_identity_match"])
        self.assertGreaterEqual(receptionist["contact_relevance_score"], 55)
        self.assertLess(receptionist["contact_relevance_score"], 75)

    def test_exact_account_target_role_scores_as_decision_maker_candidate(self):
        director = score_contact_result(
            title="Luca Bianchi - Direttore Sanitario | Brera Studio Medico",
            snippet="Direttore Sanitario presso Brera Studio Medico, Milano.",
            company_name="Brera Studio Medico",
            target_roles=["Titolare", "Medical Director", "Direttore Sanitario"],
            location_context="Milano Lombardia",
        )
        self.assertTrue(director["account_identity_match"])
        self.assertGreaterEqual(director["contact_relevance_score"], 80)
        self.assertEqual(director["contact_confidence"], "High")

    @patch("contact_discovery._search_linkedin_people")
    def test_similar_brera_organization_profile_is_held_back(self, search):
        search.return_value = [
            {
                "url": "https://it.linkedin.com/in/barbara-rivelli",
                "title": "Barbara Rivelli - Advisor IDE Istituto Dermatologico Europeo",
                "content": "Milano Lombardia Italia.",
            },
            {
                "url": "https://it.linkedin.com/in/luca-bianchi",
                "title": "Luca Bianchi - Direttore Sanitario | Brera Studio Medico",
                "content": "Direttore Sanitario presso Brera Studio Medico, Milano.",
            },
        ]

        contacts = discover_linkedin_contacts(
            company_name="Brera Studio Medico",
            country="Italy",
            target_roles=["Direttore Sanitario", "Titolare"],
            api_key="test-key",
            max_results=8,
            location_context="Milano Lombardia",
        )

        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts.iloc[0]["person_name"], "Luca Bianchi")
        self.assertTrue(bool(contacts.iloc[0]["account_identity_match"]))

    @patch("contact_discovery._search_linkedin_people")
    def test_contact_discovery_holds_back_weak_homonyms(self, search):
        search.return_value = [
            {
                "url": "https://it.linkedin.com/in/alessandra-cecchini",
                "title": "Alessandra Cecchini - Chirurgo estetico - Loconlus ONLUS",
                "content": "Milan, Lombardy, Italy. Chirurgo estetico.",
            },
            {
                "url": "https://www.linkedin.com/in/alessandra-lale-cecchini",
                "title": "Alessandra (Lale) Cecchini - Staff Scientist",
                "content": "San Diego, California, United States.",
            },
            {
                "url": "https://uk.linkedin.com/in/alessandra-cecchini-research",
                "title": "Alessandra Cecchini - Researcher",
                "content": "Greater Dundee Area, GB.",
            },
        ]

        contacts = discover_linkedin_contacts(
            company_name="Alessandra Cecchini",
            country="Italy",
            target_roles=["Titolare", "Medical Director", "Chirurgo Plastico"],
            api_key="test-key",
            max_results=8,
            location_context="Milano Lombardia",
        )

        self.assertEqual(len(contacts), 1)
        self.assertEqual(
            contacts.iloc[0]["person_name"],
            "Alessandra Cecchini",
        )
        self.assertEqual(
            int(contacts.iloc[0]["held_back_profile_count"]),
            2,
        )

if __name__ == "__main__":
    unittest.main()
