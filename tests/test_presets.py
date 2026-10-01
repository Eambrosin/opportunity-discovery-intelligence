import unittest

from presets import PRESETS, get_preset


class PresetTests(unittest.TestCase):
    def test_deleo_medical_aesthetics_is_default_first_option(self):
        self.assertEqual(
            next(iter(PRESETS)),
            "Medical Aesthetics — DELEO Test",
        )

    def test_deleo_test_keeps_medical_aesthetics_profile_id(self):
        preset = get_preset("Medical Aesthetics — DELEO Test")
        self.assertEqual(preset["profile_id"], "medical_aesthetics")
        self.assertEqual(preset["industry"], "Medical Aesthetics")
        self.assertEqual(preset["countries"], "Italy")


if __name__ == "__main__":
    unittest.main()
