#!/usr/bin/env bash
# Тесты хука block-push.sh (#129, с 27.09 push своей ветки разрешён): что отклоняется и что проходит.
# Запуск: `make hooks-test` или `bash .claude/hooks/test_block_push.sh`.
# Прогоняется на python3 из PATH и, если есть, на системном /usr/bin/python3
# (на macOS это 3.9 — хук обязан работать и на нём).
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
hook=${1:-"$here/block-push.sh"}  # абсолютный путь позволяет проверить и native Codex

# Основной набор предполагает main. Ветка рабочего репозитория не должна
# менять результат; реальные push-команды здесь никогда не исполняются.
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT
git -C "$test_root" init -q -b main || exit 1
cd "$test_root" || exit 1

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
    "echo \"\`git push\`\""
    $'cat <<EOF\n$(git push)\nEOF'
    "git push origin HEAD:main"
    "git push origin sfr-7:main"
    "git push origin refs/heads/main"
    "git push vm master"
    "git push origin :sfr-7"
    "git push --delete origin sfr-7"
    "git push -d origin sfr-7"
    "git push origin +sfr-7"
    "git push --force-with-lease origin sfr-7"
    "git push -f origin sfr-7"
    "git push -u origin sfr-7 -vf"
    "git push -u origin sfr-7 -vd"
    "git push -u origin sfr-7 --del"
    "git push -u origin sfr-7 --for"
    "git push -u origin refs/heads/*:refs/heads/*"
    "git push -u origin :"
    "git push --repo origin main"
    "git push --repo=origin master"
    "git push --all origin"
    "git push --tags origin"
    "git push --mirror origin"
    "git push --prune origin sfr-7"
    "git push -o ci.skip origin main"
    "git -c alias.p=push p origin sfr-7:main"
    "gh pr merge 1"
    "gh pr merge --auto --squash 12"
    "gh api repos/o/r/pulls/1/merge -X PUT"
    "gh api -X PATCH repos/o/r/pulls/1 -f state=closed"
    "make lint deploy-local"
    "make lint -f /private/tmp/other.mk"
    "make audit AUDIT_ARGS='--no-images; touch /private/tmp/bad'"
    "env TEST=1 make lint deploy-local"
    $'make lint deploy-local\nprintf "'
    $'gh issue edit --repo borisboriov/search-for-research 170 --repo other/repo\nprintf "'
    "gh issue edit --repo borisboriov/search-for-research 170 --repo other/repo"
    "gh pr edit --repo borisboriov/search-for-research 170 -Rother/repo"
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
    "echo '\`git push\`'"
    $'cat > f.md <<\'EOF\'\nничего не пушим: `git push` — только Борис\ngit push origin main\n$(git push)\nEOF'
    $'python3 - <<"PY"\nprint("git push")\nPY\ngit status'
    "make hooks-test"
    "git push origin sfr-7"
    "git push -u origin sfr-7"
    "git push --set-upstream origin sfr-7"
    "git push vm docs-diet"
    "git push origin sfr-7:sfr-7"
    "git push -o ci.skip origin sfr-7"
    "git push -u origin sfr-7 -vn"
    "git push -u origin sfr-7 -oci.flag"
    "git push --repo origin sfr-7"
    "git -C . push origin sfr-7"
    "git -c alias.p=push p origin sfr-7"
    "git commit -m x && git push origin sfr-7 && gh pr create --fill"
    "make lint typecheck"
    "make audit AUDIT_ARGS='--no-images --strict'"
    "gh issue edit --repo borisboriov/search-for-research 170 --body-file issue.md"
)

# Формы без явной ветки зависят от текущей ветки репозитория: проверяем во
# временных репо на ветке sfr-x (проходит) и main (отклоняется).
head_cases=(
    "git push"
    "git push origin"
    "git push -u origin"
    "git push -u origin HEAD"
    "git push origin HEAD"
    "git push origin HEAD:refs/heads/main"
)


payload() {
    python3 -c 'import json, sys; print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))' "$1"
}

payload_cwd() {
    python3 -c 'import json, sys; print(json.dumps({"tool_name": "Bash", "cwd": sys.argv[2], "tool_input": {"command": sys.argv[1]}}))' "$1" "$2"
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

# Push без явной ветки: из ветки sfr-x проходит (кроме HEAD:refs/heads/main),
# из main — отклоняется; в detached HEAD — отклоняется.
run_head_cases() {
    local tmp cmd code
    tmp=$(mktemp -d)
    git -C "$tmp" init -q -b sfr-x && git -C "$tmp" -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
    for cmd in "${head_cases[@]}"; do
        payload_cwd "$cmd" "$tmp" | bash "$hook" >/dev/null 2>&1
        code=$?
        case $cmd in
            *refs/heads/main*) [ "$code" -eq 2 ] || { echo "FAIL [ветка sfr-x] должно отклоняться (код $code): $cmd"; failures=$((failures + 1)); } ;;
            *) [ "$code" -eq 0 ] || { echo "FAIL [ветка sfr-x] должно проходить (код $code): $cmd"; failures=$((failures + 1)); } ;;
        esac
    done
    git -C "$tmp" checkout -q -b main
    for cmd in "${head_cases[@]}"; do
        payload_cwd "$cmd" "$tmp" | bash "$hook" >/dev/null 2>&1
        code=$?
        [ "$code" -eq 2 ] || { echo "FAIL [ветка main] должно отклоняться (код $code): $cmd"; failures=$((failures + 1)); }
    done
    git -C "$tmp" checkout -q --detach
    payload_cwd "git push origin HEAD" "$tmp" | bash "$hook" >/dev/null 2>&1
    [ $? -eq 2 ] || { echo "FAIL [detached HEAD] git push origin HEAD должен отклоняться"; failures=$((failures + 1)); }
    # -C на другой репозиторий: ветка берётся оттуда, а не из cwd.
    payload_cwd "git -C $tmp push origin HEAD" "/" | bash "$hook" >/dev/null 2>&1
    [ $? -eq 2 ] || { echo "FAIL [-C detached] git -C … push origin HEAD должен отклоняться"; failures=$((failures + 1)); }
    rm -rf "$tmp"
    echo "[ветка] формы без явной ветки: ${#head_cases[@]} × (sfr-x, main) + detached"
}

run_suite "python3 из PATH" ""
run_head_cases
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
    printf '%s' '{"tool_input":{"command":"make lint deploy-local"}}' | PATH=/bin /bin/bash "$hook" >/dev/null 2>&1
    [ $? -eq 2 ] || { echo "FAIL [без python3] make должен отклоняться без разбора"; failures=$((failures + 1)); }
    echo "[без python3] запасная проверка по словам push/merge"
fi

# Python есть, но падает раньше своего разбора — тот же осторожный отказ.
broken=$(mktemp -d)
printf '#!/bin/sh\nexit 1\n' > "$broken/python3"
chmod +x "$broken/python3"
payload "git -C . push" | PATH="$broken:$PATH" bash "$hook" >/dev/null 2>&1
[ $? -eq 2 ] || { echo "FAIL [python3 падает] git push должен отклоняться"; failures=$((failures + 1)); }
payload "git status" | PATH="$broken:$PATH" bash "$hook" >/dev/null 2>&1
[ $? -eq 0 ] || { echo "FAIL [python3 падает] git status должен проходить"; failures=$((failures + 1)); }
rm -rf "$broken"
echo "[python3 падает] запасная проверка по словам push/merge"

# Команда больше мегабайта: полезная нагрузка идёт через stdin, а не через
# окружение — раньше exec падал с «Argument list too long» и хук её пропускал.
big=$(python3 -c 'import json; print(json.dumps({"tool_input": {"command": "git -C . push; cat <<\x27EOF\x27\n" + "x" * 1200000 + "\nEOF"}}))')
printf '%s' "$big" | bash "$hook" >/dev/null 2>&1
[ $? -eq 2 ] || { echo "FAIL [1,2 МБ] git push в большой команде должен отклоняться"; failures=$((failures + 1)); }
big=$(python3 -c 'import json; print(json.dumps({"tool_input": {"command": "git status; cat <<\x27EOF\x27\n" + "x" * 1200000 + "\nEOF"}}))')
printf '%s' "$big" | bash "$hook" >/dev/null 2>&1
[ $? -eq 0 ] || { echo "FAIL [1,2 МБ] большая команда без push должна проходить"; failures=$((failures + 1)); }
echo "[1,2 МБ] большая команда разбирается"

# Сообщение отказа — то, что увидит агент.
msg=$(payload "git -c x=y push origin main" | bash "$hook" 2>&1 >/dev/null)
case $msg in
    *"push в main и merge — только Борис"*"push своей ветки"*) ;;
    *) echo "FAIL текст отказа: $msg"; failures=$((failures + 1)) ;;
esac

if [ "$failures" -ne 0 ]; then
    echo "провалов: $failures"
    exit 1
fi
echo "все проверки пройдены"
