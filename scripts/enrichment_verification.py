"""Compatibility entry point; implementation lives in enrichment/."""

import importlib
import sys

module = importlib.import_module("sfr_enrichment.evidence")
if __name__ == "__main__":
    module.main()
else:
    sys.modules[__name__] = module
