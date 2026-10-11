"""Compatibility entry point; implementation lives in enrichment/."""

import importlib
import sys

module = importlib.import_module("sfr_enrichment.review")
if __name__ == "__main__":
    module.main()
else:
    sys.modules[__name__] = module
