import unittest

from presets import PRESETS, get_preset


class PresetTests(unittest.TestCase):
    def test_photovoltaic_is_default_first_option(self):
        self.assertEqual(
            next(iter(PRESETS)),
            "Fotovoltaico — Distributori & EPC",
        )

    def test_photovoltaic_keeps_renewable_energy_profile_id(self):
        preset = get_preset("Fotovoltaico — Distributori & EPC")
        self.assertEqual(preset["profile_id"], "renewable_energy")
        self.assertEqual(preset["industry"], "Fotovoltaico")

    def test_medicina_estetica_keeps_medical_aesthetics_profile_id(self):
        preset = get_preset("Medicina Estetica")
        self.assertEqual(preset["profile_id"], "medical_aesthetics")
        self.assertEqual(preset["industry"], "Medicina Estetica")
        self.assertEqual(preset["countries"], "Italy")


if __name__ == "__main__":
    unittest.main()
