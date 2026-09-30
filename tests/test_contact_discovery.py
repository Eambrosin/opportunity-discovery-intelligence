import unittest
from unittest.mock import Mock, patch

from contact_discovery import (
    _account_linkedin_queries,
    _search_linkedin_people,
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


if __name__ == "__main__":
    unittest.main()
