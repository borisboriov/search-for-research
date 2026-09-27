#!/usr/bin/env bash
# Тесты хука block-push.sh (#129): что отклоняется и что проходит.
# Запуск: `make hooks-test` или `bash .claude/hooks/test_block_push.sh`.
# Прогоняется на python3 из PATH и, если есть, на системном /usr/bin/python3
# (на macOS это 3.9 — хук обязан работать и на нём).
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
hook="$here/block-push.sh"

blocked=(
    "git push"
    "git -C . push origin main"
    "git -c x=y --no-pager push"
    "git --git-dir=.git --work-tree=. push origin HEAD"
    "cd a && git push"
    "git status; git push --force"
    $'git status\ngit push'
    $'git \\\n  push origin main'
    "(cd x; git push)"
    "FOO=1 git push"
    "env GIT_TRACE=1 git push"
    "command git push"
    "nohup git push &"
    "echo x | xargs git push"
    "uv run git push"
    "/usr/bin/git push"
    "git send-pack origin"
    "git -c alias.p=push p origin main"
    "sh -c \"git push origin main\""
    "bash -lc 'git -C /tmp push'"
    "eval \"git push\""
    "echo \"\$(git push)\""
    "gh pr merge 1"
    "gh pr merge --auto --squash 12"
    "gh api repos/o/r/pulls/1/merge -X PUT"
    "gh api -X PATCH repos/o/r/pulls/1 -f state=closed"
)

allowed=(
    "git status"
    "git commit -m x"
    "git log --oneline -1"
    "git commit -m \"fix: git push в документации\""
    "git fetch origin && git status"
    "gh pr create --title t --body b"
    "gh pr view 130 --json state"
    "gh issue edit 5 --body-file x.md"
    "gh api repos/o/r/pulls/1"
    "echo \"git push\""
    "echo 'gh pr merge'"
    "grep -rn \"git push\" ."
    "ls push/"
    "make hooks-test"
)

payload() {
    python3 -c 'import json, sys; print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))' "$1"
}

failures=0
run_suite() {
    local label=$1 path_prefix=$2 cmd code
    for cmd in "${blocked[@]}"; do
        payload "$cmd" | PATH="$path_prefix$PATH" bash "$hook" >/dev/null 2>&1
        code=$?
        if [ "$code" -ne 2 ]; then
            echo "FAIL [$label] должно отклоняться (код $code): $cmd"
            failures=$((failures + 1))
        fi
    done
    for cmd in "${allowed[@]}"; do
        payload "$cmd" | PATH="$path_prefix$PATH" bash "$hook" >/dev/null 2>&1
        code=$?
        if [ "$code" -ne 0 ]; then
            echo "FAIL [$label] должно проходить (код $code): $cmd"
            failures=$((failures + 1))
        fi
    done
    echo "[$label] $(PATH="$path_prefix$PATH" python3 --version 2>&1): отклоняется ${#blocked[@]}, проходит ${#allowed[@]}"
}

run_suite "python3 из PATH" ""
if [ -x /usr/bin/python3 ]; then
    run_suite "системный python3" "/usr/bin:"
fi

# Без python3 хук закрывается осторожно: push/merge в команде — отказ.
# PATH=/bin: там есть bash и cat, но нет ни python3, ни grep (macOS).
if [ -x /bin/bash ] && ! PATH=/bin command -v python3 >/dev/null 2>&1; then
    printf '%s' '{"tool_input":{"command":"git -C . push"}}' | PATH=/bin /bin/bash "$hook" >/dev/null 2>&1
    [ $? -eq 2 ] || { echo "FAIL [без python3] git push должен отклоняться"; failures=$((failures + 1)); }
    printf '%s' '{"tool_input":{"command":"git status"}}' | PATH=/bin /bin/bash "$hook" >/dev/null 2>&1
    [ $? -eq 0 ] || { echo "FAIL [без python3] git status должен проходить"; failures=$((failures + 1)); }
    echo "[без python3] запасная проверка по словам push/merge"
fi

# Сообщение отказа — то, что увидит агент.
msg=$(payload "git -c x=y push origin main" | bash "$hook" 2>&1 >/dev/null)
case $msg in
    *"push и merge — только Борис"*) ;;
    *) echo "FAIL текст отказа: $msg"; failures=$((failures + 1)) ;;
esac

if [ "$failures" -ne 0 ]; then
    echo "провалов: $failures"
    exit 1
fi
echo "все проверки пройдены"
