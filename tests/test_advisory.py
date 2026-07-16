from __future__ import annotations

import unittest

from modules.advisory import fallback_advisory


class AdvisoryTests(unittest.TestCase):
    def test_fallback_is_bilingual_and_station_specific(self) -> None:
        advisory = fallback_advisory("Anand Vihar", 170)
        self.assertIn("English", advisory)
        self.assertIn("Hindi", advisory)
        self.assertIn("Anand Vihar", advisory)
        self.assertTrue(any("\u0900" <= character <= "\u097f" for character in advisory))


if __name__ == "__main__":
    unittest.main()
