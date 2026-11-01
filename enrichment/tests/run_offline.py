"""Run research regressions with real model transports and network blocked."""

import socket
import subprocess
import sys
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

original_popen = subprocess.Popen


def offline_popen(command: object, *args: object, **kwargs: object) -> subprocess.Popen[bytes]:
    executable = command[0] if isinstance(command, tuple | list) else str(command).split()[0]
    if Path(str(executable)).name in {"claude", "codex", "node", "pi", "curl", "wget"}:
        raise AssertionError("Offline tests require a mock for source/model/client transports")
    return cast("subprocess.Popen[bytes]", original_popen(command, *args, **kwargs))  # type: ignore[call-overload]


if __name__ == "__main__":
    directory = Path(__file__).resolve().parent
    with (
        patch("subprocess.Popen", side_effect=offline_popen),
        patch.object(
            socket.socket, "connect", side_effect=AssertionError("Offline tests: no network")
        ),
    ):
        suite = unittest.defaultTestLoader.discover(str(directory), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
