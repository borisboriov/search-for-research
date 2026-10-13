"""Compatibility entry point; implementation lives in enrichment/."""

import importlib
import sys

module = importlib.import_module("sfr_enrichment_legacy.enrichment_protocol")
if __name__ == "__main__":
    module.main()
else:
    sys.modules[__name__] = module
