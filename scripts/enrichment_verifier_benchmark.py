"""Compatibility entry point; implementation lives in enrichment/."""

import importlib
import sys

from sfr_enrichment import schema_validation
from sfr_enrichment_legacy.compat import alias_runtime

module = importlib.import_module("sfr_enrichment_legacy.enrichment_verifier_benchmark")
if __name__ == "__main__":
    module.main()
else:
    sys.modules[__name__] = alias_runtime(module, schema_validation)
