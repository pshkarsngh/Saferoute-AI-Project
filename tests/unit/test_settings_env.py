"""SafeRoute AI — tests for the .env loader and settings overrides."""

import os
import unittest
from pathlib import Path

from src.config.env import parse_env_text
from src.config.settings import load_settings

TMP = Path(__file__).resolve().parent / "_temp_env"


class TestEnvAndSettings(unittest.TestCase):
    def test_parse_env_text(self):
        text = "# c\nexport A=1\nB='two'\nC=\"three\"\nEMPTY=\nD=a=b\n"
        parsed = parse_env_text(text)
        self.assertEqual(parsed["A"], "1")
        self.assertEqual(parsed["B"], "two")
        self.assertEqual(parsed["C"], "three")
        self.assertEqual(parsed["D"], "a=b")

    def test_settings_defaults_and_env_override(self):
        env_file = TMP / ".env"
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text("SAFEROUTE_ROUTING_PROVIDER=mock\nSAFEROUTE_PORT=8123\n", encoding="utf-8")
        os.environ["SAFEROUTE_FACILITIES_PROVIDER"] = "mock"
        try:
            s = load_settings(env_path=env_file)
            self.assertEqual(s.routing_provider, "mock")
            self.assertEqual(s.port, 8123)
            self.assertEqual(s.facilities_provider, "mock")
            self.assertEqual(s.long_route_threshold_m, 100000.0)
            self.assertEqual(s.long_route_max_segments, 400)
            self.assertEqual(s.long_route_max_images_per_segment, 1)
            self.assertNotIn("mapillary_token", s.to_safe_dict())
            self.assertIn("mapillary_token_present", s.to_safe_dict())
        finally:
            os.environ.pop("SAFEROUTE_FACILITIES_PROVIDER", None)
            os.environ.pop("SAFEROUTE_ROUTING_PROVIDER", None)
            os.environ.pop("SAFEROUTE_PORT", None)
            env_file.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
