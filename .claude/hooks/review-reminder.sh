#!/usr/bin/env bash
# Stop-хук: напомнить, что закрытая итерация не прошла независимое ревью.
#
# Правило проекта (CLAUDE.md, «Артефакты сессии»): у каждой итерации есть отчёт
# `docs/SFR<N>_REPORT.md`. Ревью — отдельная сессия, скилл `/review-iteration`,
# результат `docs/REVIEW_SFR<N>.md`. Забыть его легко: отчёт написан, сессия
# кончилась, следующий тред начинает уже следующую итерацию.
#
# Хук ничего не запускает и ничего не блокирует — только печатает напоминание.
# Ревью намеренно делается в НОВОЙ сессии, а не в той, что писала код.
#
# Молчит, если:
#   * отчётов итераций нет;
#   * ревью последней итерации лежит на диске;
#   * ревью было и уже удалено — файл временный, но след остаётся в истории git;
#   * в этой сессии напоминание уже показывалось (иначе оно висело бы каждый турн).
set -uo pipefail

payload=$(cat 2>/dev/null || true)

root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$root" || exit 0

# Номер последней итерации с отчётом. Мини-итерации вида SFR4b не участвуют:
# у них нет своей нумерации ревью.
latest=$(
    ls docs/SFR[0-9]*_REPORT.md 2>/dev/null |
        sed -E 's|^docs/SFR([0-9]+)_REPORT\.md$|\1|' |
        grep -E '^[0-9]+$' | sort -n | tail -1
) || exit 0
[ -n "${latest:-}" ] || exit 0

review="docs/REVIEW_SFR${latest}.md"
[ -e "$review" ] && exit 0
git log --oneline -1 -- "$review" 2>/dev/null | grep -q . && exit 0

# Один показ на сессию: Stop срабатывает в конце каждого турна.
# session_id достаём sed'ом, а не jq: хук не должен зависеть от того,
# установлен ли jq на машине.
session=$(printf '%s' "$payload" |
    sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
stamp="${TMPDIR:-/tmp}/sfr-review-reminder-${session:-nosession}-SFR${latest}"
stamp=${stamp//[^A-Za-z0-9_.\/-]/_}
[ -e "$stamp" ] && exit 0
: >"$stamp" 2>/dev/null || true

# JSON собирается printf: в сообщении нет кавычек и обратных слэшей.
printf '{"systemMessage":"Итерация SFR-%s закрыта (docs/SFR%s_REPORT.md), независимого ревью нет. Запусти /review-iteration — по правилам проекта в НОВОЙ сессии, не в той, что писала код. Отчёт: docs/REVIEW_SFR%s.md"}\n' \
    "$latest" "$latest" "$latest"
