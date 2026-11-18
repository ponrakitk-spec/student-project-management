"""Offline deployment boundaries; no installer or cloud connection is run."""
from pathlib import Path
import json
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DeploymentManifestTests(unittest.TestCase):
    def test_vercel_runtime_dependencies_match_existing_pins(self):
        manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        expected = [line.strip() for line in (ROOT / "backend/requirements.txt").read_text(encoding="utf-16").splitlines() if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(manifest["project"]["dependencies"], expected)
        self.assertEqual(manifest["project"]["requires-python"], ">=3.12,<3.13")
        self.assertEqual(manifest["tool"]["vercel"]["entrypoint"], "backend.main:app")
        self.assertNotIn("scripts", manifest.get("tool", {}).get("vercel", {}))

    def test_api_bundle_excludes_secrets_test_fixtures_and_database_installers(self):
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(config["framework"], "fastapi")
        excluded = config["functions"]["backend/main.py"]["excludeFiles"]
        for pattern in ("**/.env*", "backend/tests/**", "database/**", "frontend/**"):
            self.assertIn(pattern, excluded)
        self.assertNotIn("buildCommand", config)
        self.assertNotIn("env", config)

    def test_frontend_is_a_separate_nextjs_project(self):
        config = json.loads((ROOT / "frontend/vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(config["framework"], "nextjs")
        self.assertNotIn("functions", config)


if __name__ == "__main__":
    unittest.main()
