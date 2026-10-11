"""Preserve old module patch targets across the runtime/orchestration split."""

from types import ModuleType
from typing import Any


def alias_runtime(legacy: ModuleType, runtime: ModuleType) -> ModuleType:
    """Old mutations reach the actual globals; the supported CLI never imports this."""
    names = frozenset(name for name in vars(runtime) if not name.startswith("__"))
    for name in names:
        if name not in vars(legacy):
            vars(legacy)[name] = getattr(runtime, name)

    class CompatibilityModule(ModuleType):
        def __setattr__(self, name: str, value: Any) -> None:
            if name in names:
                setattr(runtime, name, value)
            super().__setattr__(name, value)

        def __delattr__(self, name: str) -> None:
            if name in names:
                delattr(runtime, name)
            super().__delattr__(name)

    legacy.__class__ = CompatibilityModule
    return legacy
