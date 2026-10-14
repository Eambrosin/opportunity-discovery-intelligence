import unittest

from counterparty_roles import classify_counterparty_role


class CounterpartyRoleTests(unittest.TestCase):
    def test_buyer_role(self):
        role, _ = classify_counterparty_role(
            "Food manufacturer with production plant",
            focus="Buyers + Partners",
            target_partner_types=["Distributor", "Technical Service Partner"],
            commercial_track="Buyer Candidate",
        )
        self.assertEqual(role, "Buyer / End Customer")

    def test_route_partner_role(self):
        role, _ = classify_counterparty_role(
            "Equipment distributor serving industrial clients",
            focus="Buyers + Partners",
            target_partner_types=["Distributor"],
            commercial_track="Partner Candidate",
        )
        self.assertEqual(role, "Route-to-Market Partner")

    def test_execution_partner_role(self):
        role, _ = classify_counterparty_role(
            "Technical service provider with maintenance and spare parts",
            focus="Buyers + Partners",
            target_partner_types=["Technical Service Partner"],
            commercial_track="Partner Candidate",
        )
        self.assertEqual(role, "Execution / Technical Partner")


if __name__ == "__main__":
    unittest.main()
