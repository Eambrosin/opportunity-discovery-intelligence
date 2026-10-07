import unittest

from presets import PRESETS, get_preset


class PresetTests(unittest.TestCase):
    def test_photovoltaic_energy_consumers_is_default_first_option(self):
        self.assertEqual(
            next(iter(PRESETS)),
            "Fotovoltaico — Aziende ad Alto Consumo Energetico",
        )

    def test_photovoltaic_targets_energy_consuming_end_customers(self):
        preset = get_preset("Fotovoltaico — Aziende ad Alto Consumo Energetico")
        self.assertEqual(
            preset["profile_id"],
            "photovoltaic_energy_consumers",
        )
        self.assertEqual(
            preset["industry"],
            "Aziende ad Alto Consumo Energetico",
        )
        self.assertEqual(preset["countries"], "Italy")
        self.assertIn("stabilimento", preset["keywords"].lower())
        self.assertIn("energy manager", preset["target_roles"].lower())
        self.assertIn("installatore fotovoltaico", preset["excluded_keywords"].lower())

    def test_medicina_estetica_keeps_medical_aesthetics_profile_id(self):
        preset = get_preset("Medicina Estetica")
        self.assertEqual(preset["profile_id"], "medical_aesthetics")
        self.assertEqual(preset["industry"], "Medicina Estetica")
        self.assertEqual(preset["countries"], "Italy")


if __name__ == "__main__":
    unittest.main()
