"""Storage counts deduplicate inodes without following links or reading secrets."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from sfr_enrichment.config import repository_root


class InventoryTests(unittest.TestCase):
    def test_counts_links_and_excludes_credentials(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "storage_inventory", repository_root() / "enrichment/research/inventory.py"
        )
        assert spec and spec.loader
        inventory = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inventory)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body-fixture.bin"
            body.write_bytes(b"preserved source")
            os.link(body, root / "duplicate.bin")
            (root / "linked").symlink_to(root, target_is_directory=True)
            (root / ".env").write_bytes(b"excluded")
            (root / ".aws").mkdir()
            (root / ".aws/credentials").write_bytes(b"excluded")
            seen: set[tuple[int, int]] = set()
            row = inventory.census(root, seen)
            self.assertEqual(row["unique_files"], 1)
            self.assertEqual(row["logical_bytes"], len(b"preserved source"))
            self.assertEqual(row["allocated_bytes"], body.stat().st_blocks * 512)
            self.assertEqual(row["hardlink_aliases"], 1)
            self.assertEqual(row["symlinks_not_followed"], 1)
            self.assertEqual(row["errors"], [])
            self.assertEqual(inventory.census(root, seen)["unique_files"], 0)
