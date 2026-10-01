import unittest

from evidence_snapshot import build_relevant_evidence_snapshot


SOURCE = """
VIA FATEBENEFRATELLI 4, MILANO Tel.02 65560938
Prenota ora
+PlusSostenibilità News
Chi siamo
Il nostro spazio
Odontoiatria
Dietologia e nutrizione
Ortodonzia
Gastroenterologia
Dermatologia
Medicina estetica
Fisioterapia
Altre specialità
Il nostro team
I nostri pazienti
Odontoiatria digitale
Strumenti high tech
Materiali
# Medicina estetica
# Bellezza in salute
### LE NOSTRE PRESTAZIONI [...] Filler acido ialuronico
Biorevitalizzazione e biostimolazione Peeling Foto-ringiovanimento Tossina botulinica Lifting no bisturi
### Trattamenti non chirurgici
I nostri medici chirurghi specializzati in medicina estetica propongono cure e trattamenti non chirurgici, dedicati in modo particolare al viso per correzione di inestetismi e riduzione e prevenzione dei segni dell’invecchiamento.
"""


class EvidenceSnapshotTests(unittest.TestCase):
    def test_keeps_contact_and_commercial_evidence(self):
        snapshot = build_relevant_evidence_snapshot(SOURCE)

        self.assertTrue(
            any("FATEBENEFRATELLI" in line for line in snapshot["contact_lines"])
        )
        joined = " ".join(snapshot["commercial_evidence"]).lower()
        self.assertIn("filler acido ialuronico", joined)
        self.assertIn("biorevitalizzazione", joined)
        self.assertIn("trattamenti non chirurgici", joined)

    def test_removes_navigation_noise(self):
        snapshot = build_relevant_evidence_snapshot(SOURCE)
        joined = " ".join(
            snapshot["contact_lines"] + snapshot["commercial_evidence"]
        ).lower()

        self.assertNotIn("prenota ora", joined)
        self.assertNotIn("chi siamo", joined)
        self.assertNotIn("odontoiatria digitale", joined)
        self.assertNotIn("materiali", joined)

    def test_has_fallback_when_no_relevant_lines_exist(self):
        snapshot = build_relevant_evidence_snapshot(
            "A generic paragraph about a business with no target treatment terms."
        )
        self.assertEqual(snapshot["contact_lines"], [])
        self.assertEqual(snapshot["commercial_evidence"], [])
        self.assertTrue(snapshot["fallback_preview"])


if __name__ == "__main__":
    unittest.main()
