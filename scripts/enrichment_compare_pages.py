"""Compatibility entry point; implementation lives in enrichment/."""

import importlib
import sys

from sfr_enrichment import http_policy
from sfr_enrichment_legacy.compat import alias_runtime

module = importlib.import_module("sfr_enrichment_legacy.enrichment_compare_pages")
if __name__ == "__main__":
    module.main()
else:
    sys.modules[__name__] = alias_runtime(module, http_policy)
