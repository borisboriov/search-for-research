"""Allowlisted historical PDF parser replay, never a fresh-source decoder."""

import hashlib
import subprocess
import sys
from pathlib import Path

from sfr_enrichment.common import read, sha


def legacy_pdf_text(root: Path, raw: bytes) -> str:
    """Historical parser ONLY for checksum-allowlisted sealed baseline PDFs.

    Fresh sources always use the current locked parser. This is version replay,
    not acceptance of an unverified cached decoding or an audit exception.
    """
    manifest = read(root / "manifest.json")
    if hashlib.sha256(raw).hexdigest() not in manifest["baseline_pdf_body_sha256"]:
        raise ValueError("Historical parser cannot process a new PDF")
    support = root / "baseline-pdf-parser"
    for name, digest in manifest["baseline_pdf_parser_sha256"].items():
        if sha(support / name) != digest:
            raise ValueError("Historical parser snapshot changed")
    code = (
        "import sys,io;sys.path.insert(0,sys.argv[1]);import pypdf;"
        "r=pypdf.PdfReader(io.BytesIO(sys.stdin.buffer.read()));"
        "assert not r.is_encrypted and len(r.pages)<=100;"
        "t='\\n'.join(p.extract_text() or '' for p in r.pages);"
        "assert len(t)<=1000000;sys.stdout.buffer.write(t.encode())"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-I", "-c", code, str(support)],
        input=raw,
        capture_output=True,
        timeout=15,
        check=True,
    )
    return result.stdout.decode()
