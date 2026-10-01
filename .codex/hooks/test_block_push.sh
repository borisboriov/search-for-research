#!/usr/bin/env bash
# One shared regression suite, executed against the native Codex hook.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
exec bash "$root/.claude/hooks/test_block_push.sh" "$root/.codex/hooks/block-push.sh"
