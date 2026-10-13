"""Compatibility entry point; implementation lives in enrichment/."""

import importlib
import sys

from sfr_enrichment import replay
from sfr_enrichment_legacy.compat import alias_runtime

module = importlib.import_module("sfr_enrichment_legacy.enrichment_glm_compare")
if __name__ == "__main__":
    pass
else:
    sys.modules[__name__] = alias_runtime(module, replay)
