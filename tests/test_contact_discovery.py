import unittest
from unittest.mock import Mock, patch

from contact_discovery import (
    _account_linkedin_queries,
    _extract_honorific_names,
    _merge_contact_sources,
    _search_linkedin_people,
    discover_account_contacts,
    discover_linkedin_contacts,
    discover_official_site_contacts,
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


    def test_extracts_named_people_from_official_site_text(self):
        names = _extract_honorific_names(
            "Il Dott. Fabrizio Cecchini è il direttore sanitario. "
            "Dott. Maria Teresa Grecchi medico chirurgo specialista in medicina estetica."
        )
        self.assertIn("Fabrizio Cecchini", names)
        self.assertIn("Maria Teresa Grecchi", names)

    @patch("contact_discovery._search_official_site")
    def test_official_site_discovery_prioritizes_explicit_decision_authority(self, search):
        search.return_value = [
            {
                "url": "https://brerastudiomedico.it/il-nostro-team.php",
                "title": "Brera Studio Medico | Il nostro team",
                "content": (
                    "Dott. Fabrizio Cecchini Medico chirurgo. "
                    "Il dottor Fabrizio Cecchini è il direttore sanitario di Brera Studio Medico. "
                    "Dott. Maria Teresa Grecchi medico chirurgo specialista in medicina estetica."
                ),
                "search_query": '"Brera Studio Medico" "direttore sanitario"',
            }
        ]

        contacts = discover_official_site_contacts(
            company_name="Brera Studio Medico",
            account_website="https://www.brerastudiomedico.it",
            source_url="https://www.brerastudiomedico.it/medicina-estetica.php",
            target_roles=["Direttore Sanitario", "Medico Estetico"],
            api_key="test-key",
            max_results=8,
        )

        self.assertGreaterEqual(len(contacts), 2)
        self.assertEqual(contacts.iloc[0]["person_name"], "Fabrizio Cecchini")
        self.assertTrue(bool(contacts.iloc[0]["decision_authority_signal"]))
        self.assertEqual(contacts.iloc[0]["contact_confidence"], "High")
        self.assertIn("Direttore Sanitario", contacts.iloc[0]["matched_target_roles"])

        doctor = contacts[
            contacts["person_name"] == "Maria Teresa Grecchi"
        ].iloc[0]
        self.assertFalse(bool(doctor["decision_authority_signal"]))
        self.assertEqual(doctor["professional_role_signal"], "medico estetico")

    @patch("contact_discovery.discover_linkedin_contacts")
    @patch("contact_discovery.discover_official_site_contacts")
    def test_account_contact_discovery_skips_broad_linkedin_when_official_authority_exists(
        self,
        official_search,
        linkedin_search,
    ):
        import pandas as pd

        official_search.return_value = pd.DataFrame(
            [
                {
                    "person_name": "Fabrizio Cecchini",
                    "headline": "Direttore Sanitario",
                    "source_type": "Official site",
                    "contact_relevance_score": 100,
                    "contact_confidence": "High",
                    "decision_authority_signal": True,
                    "linkedin_url": "",
                }
            ]
        )

        contacts = discover_account_contacts(
            company_name="Brera Studio Medico",
            account_website="https://www.brerastudiomedico.it",
            source_url="https://www.brerastudiomedico.it/medicina-estetica.php",
            country="Italy",
            target_roles=["Direttore Sanitario", "Medico Estetico"],
            api_key="test-key",
            location_context="Milano Lombardia",
        )

        linkedin_search.assert_not_called()
        self.assertEqual(len(contacts), 1)
        self.assertTrue(bool(contacts.iloc[0]["decision_authority_signal"]))

    def test_merge_preserves_official_role_and_adds_linkedin_corroboration(self):
        import pandas as pd

        official = pd.DataFrame(
            [
                {
                    "person_name": "Fabrizio Cecchini",
                    "headline": "Direttore Sanitario",
                    "linkedin_url": "",
                    "source_type": "Official site",
                    "contact_relevance_score": 100,
                    "contact_confidence": "High",
                    "decision_authority_signal": True,
                    "why_contact": "official account-domain evidence",
                }
            ]
        )
        linkedin = pd.DataFrame(
            [
                {
                    "person_name": "Fabrizio Cecchini",
                    "headline": "Medico Chirurgo",
                    "linkedin_url": "https://it.linkedin.com/in/fabrizio-cecchini",
                    "source_type": "Person",
                    "contact_relevance_score": 85,
                    "contact_confidence": "High",
                    "decision_authority_signal": False,
                }
            ]
        )
        linkedin["raw_profile_count"] = 1
        linkedin["held_back_profile_count"] = 0

        merged = _merge_contact_sources(official, linkedin, max_results=8)

        self.assertEqual(len(merged), 1)
        self.assertEqual(
            merged.iloc[0]["linkedin_url"],
            "https://it.linkedin.com/in/fabrizio-cecchini",
        )
        self.assertEqual(
            merged.iloc[0]["source_type"],
            "Official site + LinkedIn",
        )
        self.assertTrue(bool(merged.iloc[0]["decision_authority_signal"]))

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
