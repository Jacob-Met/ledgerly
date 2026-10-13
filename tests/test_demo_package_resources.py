"""Keep the installed demo's packaged examples tied to the source fixtures."""
from importlib.resources import files
from pathlib import Path
import unittest


class DemoPackageResourceTests(unittest.TestCase):
    def test_demo_inputs_are_complete_and_match_canonical_fixture_bytes(self):
        expected = {
            "01_simple_usd_hourly.txt",
            "04_multi_currency.txt",
            "05_missing_email.txt",
            "12_prompt_injection.txt",
        }
        packaged = files("ledgerly._demo_fixtures")
        canonical = Path(__file__).resolve().parents[1] / "fixtures"
        self.assertEqual({item.name for item in packaged.iterdir() if item.name.endswith(".txt")}, expected)
        for name in sorted(expected):
            with self.subTest(fixture=name):
                self.assertEqual(packaged.joinpath(name).read_bytes(), (canonical / name).read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
