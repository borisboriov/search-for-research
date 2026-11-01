"""Tools-only local transport amendment does not replace sanctioned instructions."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sfr_enrichment import native
from sfr_enrichment.common import sha


class CatalogIsolationTests(unittest.TestCase):
    def test_exact_capability_diff_and_hashes_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = root / "codex"
            binary.write_bytes(b"fixed-executable")
            original = root / "original.json"
            isolated = root / "isolated.json"
            amendment = root / "amendment.json"
            model = {
                "slug": "gpt-6.1-sol",
                "tool_mode": "code_mode_only",
                "multi_agent_version": "v2",
                "apply_patch_tool_type": "freeform",
                "experimental_supported_tools": ["clock"],
                "base_instructions": "mandatory unchanged",
                "context_window": 123,
                "use_responses_lite": True,
            }
            before = {"models": [model, {"slug": "other", "base_instructions": "also unchanged"}]}
            original.write_text(json.dumps(before))
            after = json.loads(json.dumps(before))
            after["models"][0].update(
                tool_mode="direct",
                multi_agent_version="disabled",
                apply_patch_tool_type=None,
                experimental_supported_tools=[],
            )
            isolated.write_text(json.dumps(after))
            config = {
                "original_catalog_path": str(original),
                "isolated_catalog_path": str(isolated),
                "original_catalog_sha256": sha(original),
                "isolated_catalog_sha256": sha(isolated),
                "cli_binary_sha256": sha(binary),
                "native_sha256": sha(Path(native.__file__)),
                "cli_version": "fixture",
                "implementation_revision": "fixture",
            }
            amendment.write_text(json.dumps(config))
            with (
                patch("sfr_enrichment.native.shutil.which", return_value=str(binary)),
                patch(
                    "sfr_enrichment.native.subprocess.run",
                    return_value=subprocess.CompletedProcess(
                        [], 0, stdout=b"incremental_tools stable true\n", stderr=b""
                    ),
                ) as features,
            ):
                options, proof = native.isolated_catalog_options(
                    root / "out", "gpt-6.1-sol", amendment
                )
                self.assertIn("agents.enabled=false", options)
                self.assertEqual(proof["execution_amendment_sha256"], sha(amendment))
                self.assertEqual(
                    (root / "out/isolated-model-catalog.json").read_bytes(), isolated.read_bytes()
                )
                features.return_value = subprocess.CompletedProcess(
                    [], 0, stdout=b"incremental_tools stable false\n"
                )
                with self.assertRaisesRegex(ValueError, "inventory is not enabled"):
                    native.isolated_catalog_options(root / "disabled", "gpt-6.1-sol", amendment)
                features.return_value = subprocess.CompletedProcess(
                    [], 0, stdout=b"incremental_tools stable true\n"
                )
                for field, value in [("base_instructions", "replaced"), ("context_window", 999)]:
                    changed = json.loads(json.dumps(after))
                    changed["models"][0][field] = value
                    isolated.write_text(json.dumps(changed))
                    config["isolated_catalog_sha256"] = sha(isolated)
                    amendment.write_text(json.dumps(config))
                    with self.assertRaisesRegex(ValueError, "beyond tool capabilities"):
                        native.isolated_catalog_options(root / "bad", "gpt-6.1-sol", amendment)
                isolated.write_text(json.dumps(after))
                config["isolated_catalog_sha256"] = sha(isolated)
                amendment.write_text(json.dumps(config))
                binary.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "executable changed"):
                    native.isolated_catalog_options(root / "bad", "gpt-6.1-sol", amendment)
