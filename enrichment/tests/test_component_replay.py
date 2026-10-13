"""Saved-source replay keeps evidence and human comparison separate."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "research/components/offline_components.py"
spec = importlib.util.spec_from_file_location("component_replay", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ComponentReplayTests(unittest.TestCase):
    def test_outputs_cannot_overwrite_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "proof.json"
            module.save(path, {"first": True})
            with self.assertRaises(FileExistsError):
                module.save(path, {"first": False})
            self.assertEqual(module.read(path), {"first": True})

    def test_control_keeps_mailto_quote_but_does_not_execute_js(self) -> None:
        html = '<a href="mailto:p%40example.org">Contact</a><script>x@y.org</script>'
        text, extras = module.parse("control", html.encode(), html, "https://example.org")
        self.assertNotIn("x@y.org", text)
        self.assertEqual(extras[0]["value"], "p@example.org")
        self.assertIn("mailto:p%40example.org", extras[0]["quote"])

    def test_orcid_only_public_person_email(self) -> None:
        import json

        raw = json.dumps(
            {
                "person": {
                    "emails": {
                        "email": [
                            {"email": "p@example.org", "visibility": "public"},
                            {"email": "secret@example.org", "visibility": "limited"},
                        ]
                    }
                },
                "works": "foreign@example.org",
            }
        ).encode()
        text, _ = module.parse("orcid-json", raw, "", "https://example.org")
        self.assertEqual(text, "p@example.org")

    def test_no_network_guard(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "forbids network"):
            module.blocked("https://example.org")

    def test_evaluation_rejects_changed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module.save(root / "manifest.json", {})
            module.save(root / "replay.json", {"manifest_sha256": "wrong"})
            with self.assertRaisesRegex(ValueError, "Manifest changed"):
                module.evaluate(root, root / "never-read-human.json")


if __name__ == "__main__":
    unittest.main()
