"""Saved-source replay keeps evidence and human comparison separate."""

import importlib.util
import sys
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

    def test_existing_flexible_rule_retains_original_spans(self) -> None:
        from sfr_enrichment.contacts import flexible_email_matches

        text = "Contact: somebody\u00a0 @  example.org; no guessing"
        matches = list(flexible_email_matches(text))
        self.assertEqual(matches[0][0], "somebody@example.org")
        self.assertEqual(text[matches[0][1] : matches[0][2]], "somebody\u00a0 @  example.org")
        self.assertEqual(list(flexible_email_matches("somebody at example.org")), [])

    def test_adapter_rejects_changed_cached_decoder(self) -> None:
        sys.modules["offline_components"] = module
        adapter_spec = importlib.util.spec_from_file_location(
            "adapted_control", SCRIPT.parent / "adapted_control.py"
        )
        assert adapter_spec is not None and adapter_spec.loader is not None
        adapter = importlib.util.module_from_spec(adapter_spec)
        adapter_spec.loader.exec_module(adapter)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            module.save(path, {})
            script = Path(tmp) / "script.js"
            script.write_bytes(b"arbitrary JS is not executed")
            body = (
                '<script src="/func_string.js"></script>'
                '<script>document.write(decode_email("AA"))</script>'
            )
            receipts = {
                "https://example.org/func_string.js": {
                    "receipt_path": str(path),
                    "receipt_sha256": module.sha(path.read_bytes()),
                    "body_path": str(script),
                    "body_sha256": "wrong",
                }
            }
            with self.assertRaisesRegex(ValueError, "Frozen decoder changed"):
                adapter.preprocess(body, "https://example.org/page", receipts)

    def test_original_quote_binding_preserves_crlf_offsets(self) -> None:
        sys.modules["offline_components"] = module
        adapter_spec = importlib.util.spec_from_file_location(
            "adapted_control", SCRIPT.parent / "adapted_control.py"
        )
        assert adapter_spec is not None and adapter_spec.loader is not None
        adapter = importlib.util.module_from_spec(adapter_spec)
        adapter_spec.loader.exec_module(adapter)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decoded = root / "decoded.txt"
            raw = b"Heading\r\nContact: person@example.org\r\n"
            decoded.write_bytes(raw)
            url = "https://example.org/page"
            module.save(
                root / "manifest.json",
                {
                    "sources": [
                        {
                            "url": url,
                            "decoded_path": str(decoded),
                            "decoded_sha256": module.sha(raw),
                        }
                    ]
                },
            )
            module.save(root / "adaptation.json", {})
            module.save(
                root / "replay.json",
                {
                    "rows": [
                        {
                            "url": url,
                            "author_id": "A1",
                            "tool": "control",
                            "body_sha256": "body",
                            "candidates": [{"value": "person@example.org", "quote": "derived"}],
                        }
                    ]
                },
            )
            adapter.bind_original_quotes(root, transforms_by_url={})
            binding = module.read(root / "preprocessing-provenance.json")["rows"][0][
                "original_binding"
            ]
            original = raw.decode()
            self.assertEqual(binding["start"], original.index("person@example.org"))
            self.assertEqual(original[binding["start"] : binding["end"]], binding["original_quote"])

    def test_entity_binding_retains_original_html_quote(self) -> None:
        sys.modules["offline_components"] = module
        binder_spec = importlib.util.spec_from_file_location(
            "bind_entity_quotes", SCRIPT.parent / "bind_entity_quotes.py"
        )
        assert binder_spec is not None and binder_spec.loader is not None
        binder = importlib.util.module_from_spec(binder_spec)
        binder_spec.loader.exec_module(binder)
        original = "Heading\nContact: person&#64;example.org\n"
        binding = binder.original_line(original, "person@example.org")
        self.assertEqual(binding["original_quote"], "Contact: person&#64;example.org\n")
        self.assertEqual(original[binding["start"] : binding["end"]], binding["original_quote"])
        self.assertIsNone(binder.original_line(original, "other@example.org"))

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
