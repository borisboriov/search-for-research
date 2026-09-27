#!/usr/bin/env bash
# PreToolUse-хук для Bash: push в main, force/delete и merge — только Борис
# (CLAUDE.md, DECISIONS 27.09, #129); push своей ветки сессии разрешён (27.09, #140).
#
# Запрет `Bash(git push *)` в settings.json — префиксное правило: `git -C . push`,
# `git -c k=v push`, `cd x && git push` его обходят. Этот хук — граница: он
# разбирает команду на отдельные вызовы (`&&`, `||`, `;`, `|`, `&`, переносы
# строк, скобки, `sh -c` / `bash -lc` / `eval`, подстановки `$(…)` и `` `…` ``,
# обёртки `env`, `command`, `nohup`, `timeout`, `xargs`, `uv run` и т. п.) и
# отклоняет вызов, если это
#   * `git … push`, который не является пушем своей ветки: без явной ветки из
#     `main` (или когда текущую ветку не определить), с назначением `main` /
#     `master` (`origin main`, `HEAD:main`, `refs/heads/main`), с `--force`,
#     `--force-with-lease`, `+refspec`, `--delete` / `:ветка`, `--all`, `--tags`,
#     `--mirror`, `--prune`; `git … send-pack` — всегда. Глобальные опции git
#     (`-C`, `-c`, `--git-dir`, …) и алиасы (`git -c alias.p=push p`, алиас из
#     git config) разбираются. Разрешено: `git push origin <ветка>`,
#     `git push -u origin HEAD` не из `main`;
#   * `gh pr merge`;
#   * `gh api`, меняющий PR: эндпоинт `…/pulls/N/merge`, методы PUT/PATCH/DELETE
#     на `…/pulls…`, GraphQL-мутации слияния.
# Строки в кавычках — это строки: `echo "git push"` проходит; тело heredoc с
# кавычками у разделителя (`<<'EOF'`) — литерал, тело без кавычек проверяется
# только на подстановки `$(…)` / `` `…` ``, которые bash в нём выполнит.
#
# Протокол Claude Code: отказ — код 2 и причина в stderr (её видит агент),
# пропуск — код 0 без вывода. Разбор — python3 из системы; если его нет или
# разбор упал, хук закрывается осторожно: блокирует любую команду, где есть
# слова push или merge (лучше лишний отказ, чем тихий пропуск).
#
# Тесты — .claude/hooks/test_block_push.sh (`make hooks-test`).
set -uo pipefail

payload=$(cat 2>/dev/null || true)
reason_prefix="push в main и merge — только Борис (CLAUDE.md, DECISIONS 27.09)"

# Осторожный отказ без разбора: только встроенные средства bash — без python3
# может не оказаться и grep.
fallback() {
    shopt -s nocasematch
    if [[ $payload == *push* || $payload == *merge* ]]; then
        echo "$reason_prefix: $1, команда с push/merge отклонена без разбора" >&2
        exit 2
    fi
    exit 0
}

command -v python3 >/dev/null 2>&1 || fallback "python3 не найден"

# Скрипт — аргументом `-c`, команда — через stdin: переменная окружения или
# аргумент упёрлись бы в лимит размера (у команды больше ~1 МБ exec падал с
# «Argument list too long», и хук молча пропускал её).
read -r -d '' script <<'PY' || true
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

PREFIX = "push в main и merge — только Борис (CLAUDE.md, DECISIONS 27.09)"
SEPARATORS = {";", "&&", "||", "|", "&", "|&", ";;", "(", ")", "{", "}", "\n"}
KEYWORDS = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "!", "time"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
# Обёртки, после которых идёт настоящая команда: ищем git/gh среди их аргументов.
WRAPPERS = {
    "env", "command", "builtin", "exec", "nohup", "nice", "timeout", "sudo", "doas",
    "xargs", "stdbuf", "caffeinate", "uv", "uvx", "npx", "watch", "time",
}
# Глобальные опции git, у которых значение — отдельным словом.
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
PUSH_SUBCOMMANDS = {"push", "send-pack"}
MUTATING = {"PUT", "PATCH", "DELETE"}
# Ветки, в которые сессия не пушит ни в какой форме.
PROTECTED = {"main", "master", "refs/heads/main", "refs/heads/master"}
# Опции push, которые переписывают историю или трогают чужие ветки.
PUSH_FORBIDDEN_OPTS = {
    "-f", "--force", "--force-with-lease", "--force-if-includes", "-d", "--delete",
    "--mirror", "--all", "--branches", "--tags", "--follow-tags", "--prune",
}
# Опции push, у которых значение — отдельным словом (если не через `=`).
PUSH_OPTS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}


def tokenize(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


HEREDOC = re.compile(r"(?<!<)<<-?\s*(['\"]?)([A-Za-z0-9_]+)\1(?!<)")


def split_heredocs(command: str) -> tuple[str, list[str]]:
    """Отделить тела heredoc от команды.

    Тело — не команда: `cat > f <<'EOF'` с текстом «git push» внутри ничего не
    пушит. Тело с кавычками у разделителя (`<<'EOF'`) — литерал, его не
    смотрим вовсе; без кавычек (`<<EOF`) bash выполняет в нём `$(…)` и `` `…` ``,
    поэтому такие тела возвращаются для поиска подстановок.
    """
    code: list[str] = []
    bodies: list[str] = []
    pending: list[tuple[str, bool, list[str]]] = []
    for line in command.split("\n"):
        if pending:
            delim, quoted, buf = pending[0]
            if line.strip() == delim:
                pending.pop(0)
                if not quoted:
                    bodies.append("\n".join(buf))
            else:
                buf.append(line)
            continue
        code.append(line)
        for match in HEREDOC.finditer(line):
            pending.append((match.group(2), bool(match.group(1)), []))
    bodies.extend("\n".join(buf) for _, quoted, buf in pending if not quoted)
    return "\n".join(code), bodies


def substitutions(text: str, quotes: bool = True) -> list[str]:
    """Содержимое `$(…)` и `` `…` ``, которые bash выполнит.

    В одинарных кавычках подстановок нет, в двойных — есть. `quotes=False` —
    для тела heredoc без кавычек: там кавычки — обычные символы.
    """
    found: list[str] = []
    i, n, state = 0, len(text), "plain"
    while i < n:
        ch = text[i]
        if state == "single":
            if ch == "'":
                state = "plain"
            i += 1
            continue
        if ch == "\\":
            i += 2
            continue
        if quotes and ch == "'" and state == "plain":
            state = "single"
        elif quotes and ch == '"':
            state = "double" if state == "plain" else "plain"
        elif text.startswith("$(", i):
            depth, j = 1, i + 2
            while j < n and depth:
                depth += {"(": 1, ")": -1}.get(text[j], 0)
                j += 1
            found.append(text[i + 2 : j - 1])
            i = j
            continue
        elif ch == "`":
            end = text.find("`", i + 1)
            end = n if end == -1 else end
            found.append(text[i + 1 : end])
            i = end + 1
            continue
        i += 1
    return found


def segments(tokens: list[str]) -> list[list[str]]:
    out: list[list[str]] = [[]]
    for token in tokens:
        if token in SEPARATORS or set(token) <= set(";&|()<>\n"):
            out.append([])
        else:
            out[-1].append(token)
    return [seg for seg in out if seg]


def strip_prefix(argv: list[str]) -> list[str]:
    """Убрать ключевые слова и присваивания `VAR=значение` в начале вызова."""
    i = 0
    while i < len(argv) and (
        argv[i] in KEYWORDS or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", argv[i])
    ):
        i += 1
    return argv[i:]


def git_alias(name: str, cwd: str | None, inline: dict[str, str]) -> str | None:
    if name in inline:
        return inline[name]
    try:
        result = subprocess.run(
            ["git", "config", "--get", f"alias.{name}"],
            capture_output=True, text=True, timeout=5, cwd=cwd or None, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def current_branch(cwd: str | None, git_global: list[str]) -> str | None:
    """Текущая ветка репозитория (None — detached HEAD или git не ответил)."""
    try:
        result = subprocess.run(
            ["git", *git_global, "symbolic-ref", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=cwd or None, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def check_push(args: list[str], cwd: str | None, git_global: list[str]) -> str | None:
    """`git push …` пропускается только как push своей ветки.

    Запрещены force/delete/all/tags/mirror/prune, принудительный `+refspec`,
    удаление `:ветка`, любое назначение из PROTECTED. Без явной ветки
    (`git push`, `git push -u origin`, `HEAD`) назначение — текущая ветка
    репозитория: из `main` или при detached HEAD — отказ.
    """
    positional: list[str] = []
    j = 0
    while j < len(args):
        arg = args[j]
        if arg == "--":
            positional.extend(args[j + 1:])
            break
        if arg.startswith("-"):
            base = arg.split("=", 1)[0]
            if base in PUSH_FORBIDDEN_OPTS or base.startswith("--force"):
                return f"git push {base}"
            if base in PUSH_OPTS_WITH_VALUE and "=" not in arg:
                j += 2
                continue
            j += 1
            continue
        positional.append(arg)
        j += 1
    refspecs = positional[1:]
    if not refspecs:
        branch = current_branch(cwd, git_global)
        if not branch:
            return "git push без явной ветки (текущую ветку определить не удалось)"
        if branch in PROTECTED:
            return f"git push из ветки {branch}"
        return None
    for spec in refspecs:
        if spec.startswith("+"):
            return f"git push {spec} (принудительно)"
        src, sep, dst = spec.partition(":")
        if sep and not src:
            return f"git push {spec} (удаление ветки)"
        target = dst if sep else src
        if target == "HEAD":
            target = current_branch(cwd, git_global) or ""
            if not target:
                return "git push HEAD (текущую ветку определить не удалось)"
        if target in PROTECTED:
            return f"git push … {spec} (в {target})"
    return None


def check_git(argv: list[str], cwd: str | None, depth: int) -> str | None:
    i, inline_aliases = 1, {}
    while i < len(argv):
        arg = argv[i]
        if arg in GIT_OPTS_WITH_VALUE:
            if arg == "-c" and i + 1 < len(argv):
                key, _, value = argv[i + 1].partition("=")
                if key.lower().startswith("alias."):
                    inline_aliases[key[len("alias."):]] = value
            i += 2
            continue
        if arg.startswith("-"):
            i += 1
            continue
        break
    if i >= len(argv):
        return None
    sub = argv[i]
    if sub == "send-pack":
        return "git send-pack"
    if sub == "push":
        return check_push(argv[i + 1:], cwd, argv[1:i])
    alias = git_alias(sub, cwd, inline_aliases)
    if alias:
        if alias.startswith("!"):
            return check_command(alias[1:], cwd, depth + 1)
        words = alias.split()
        if words and words[0] == "send-pack":
            return f"git {sub} (алиас «{alias}»)"
        if words and words[0] == "push":
            found = check_push(words[1:] + argv[i + 1:], cwd, argv[1:i])
            return f"{found} (алиас «{alias}»)" if found else None
    return None


def check_gh(argv: list[str]) -> str | None:
    words = [a for a in argv[1:] if not a.startswith("-")]
    if words[:2] == ["pr", "merge"]:
        return "gh pr merge"
    if words[:1] != ["api"]:
        return None
    method, endpoint, rest = None, None, argv[argv.index("api") + 1:]
    j = 0
    while j < len(rest):
        arg = rest[j]
        if arg in ("-X", "--method") and j + 1 < len(rest):
            method = rest[j + 1].upper()
            j += 2
            continue
        if arg.startswith("--method="):
            method = arg.split("=", 1)[1].upper()
        elif arg.startswith("-X") and len(arg) > 2:
            method = arg[2:].upper()
        elif not arg.startswith("-") and endpoint is None:
            endpoint = arg
        j += 1
    endpoint = endpoint or ""
    if re.search(r"pulls/\d+/merge\b", endpoint):
        return f"gh api {endpoint}"
    if method in MUTATING and "pulls" in endpoint:
        return f"gh api -X {method} {endpoint}"
    if endpoint == "graphql" and any(
        re.search(r"mergePullRequest|enablePullRequestAutoMerge", a) for a in rest
    ):
        return "gh api graphql (слияние PR)"
    return None


def check_argv(argv: list[str], cwd: str | None, depth: int) -> str | None:
    argv = strip_prefix(argv)
    if not argv:
        return None
    name = os.path.basename(argv[0])
    if name == "git":
        return check_git(argv, cwd, depth)
    if name == "gh":
        return check_gh(argv)
    if name in SHELLS:
        for k, arg in enumerate(argv[1:], start=1):
            if arg.startswith("-") and "c" in arg[1:] and not arg.startswith("--"):
                if k + 1 < len(argv):
                    return check_command(argv[k + 1], cwd, depth + 1)
        return None
    if name == "eval":
        return check_command(" ".join(argv[1:]), cwd, depth + 1)
    if name in WRAPPERS:
        for k in range(1, len(argv)):
            if os.path.basename(argv[k]) in ("git", "gh") or argv[k] in SHELLS:
                return check_argv(argv[k:], cwd, depth)
    return None


def check_command(command: str, cwd: str | None, depth: int = 0) -> str | None:
    if depth > 5:
        return None
    # Перенос строки с обратным слэшем — продолжение команды, как в bash.
    code, bodies = split_heredocs(command.replace("\\\n", " "))
    inner_commands = substitutions(code)
    for body in bodies:
        inner_commands += substitutions(body, quotes=False)
    for inner in inner_commands:
        found = check_command(inner, cwd, depth + 1)
        if found:
            return found
    for argv in segments(tokenize(code)):
        found = check_argv(argv, cwd, depth)
        if found:
            return found
    return None


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or not command.strip():
        return 0
    try:
        found = check_command(command, payload.get("cwd"))
    except Exception as exc:  # noqa: BLE001 — хук-граница: при сбое разбора закрыться
        if re.search(r"push|merge", command, re.IGNORECASE):
            print(f"{PREFIX}: не удалось разобрать команду ({exc}), в ней есть push/merge", file=sys.stderr)
            return 2
        return 0
    if found:
        print(
            f"{PREFIX}: отклонено «{found}». Разрешён только push своей ветки — "
            "`git push origin <ветка>` не из main, без --force/--delete; PR — `gh pr create`; "
            "push в main, merge и выкладка — Борис. "
            "Если это текст, а не вызов (сообщение коммита, markdown): обратные кавычки "
            "и $(…) внутри \"…\" bash выполняет — передай текст файлом или heredoc в "
            "кавычках (git commit -F - <<'MSG').",
            file=sys.stderr,
        )
        return 2
    return 0


sys.exit(main())
PY

printf '%s' "$payload" | python3 -c "$script"
code=$?
# 0 — пропуск, 2 — отказ. Любой другой код — python упал раньше своего разбора
# (синтаксис, память): закрываемся так же, как без python3.
[ "$code" -eq 0 ] || [ "$code" -eq 2 ] && exit "$code"
fallback "разбор команды упал (код $code)"
