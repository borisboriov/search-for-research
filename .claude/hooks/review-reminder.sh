#!/usr/bin/env bash
# Stop-хук: напомнить, что закрытая итерация не прошла независимое ревью.
#
# Правило проекта (CLAUDE.md, «Артефакты сессии»): у каждой итерации есть отчёт
# `docs/SFR<N>_REPORT.md`. Ревью делает субагент `sfr-reviewer` (`/review-iteration`),
# его находки уходят в issues `from-review`, а итог — в раздел отчёта с заголовком
# «… ревью …» (§11 SFR-5, §12 SFR-5b/5c, §7 SFR-6). Старый след — файл
# `docs/REVIEW_SFR<N>.md` (в истории git, сейчас не коммитится) — тоже принимается.
#
# Хук ничего не запускает и ничего не блокирует — только печатает напоминание.
#
# Молчит, если:
#   * отчётов итераций нет;
#   * в последнем по дате коммита отчёте (мини-итерации SFR5b/SFR5c — наравне
#     с числовыми) есть раздел «ревью» хотя бы из трёх строк текста;
#   * есть или был в истории git файл `docs/REVIEW_SFR<тег>.md`;
#   * в этой сессии напоминание уже показывалось (иначе висело бы каждый турн).
set -uo pipefail

payload=$(cat 2>/dev/null || true)

root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$root" || exit 0

# Последний отчёт — по дате последнего коммита файла, а не по номеру: SFR-5c
# (26.09) моложе SFR-6 (12.09). Не закоммиченный ещё отчёт — по mtime.
latest="" latest_ts=0
for f in docs/SFR*_REPORT.md; do
    [ -e "$f" ] || continue
    ts=$(git log -1 --format=%ct -- "$f" 2>/dev/null || true)
    # GNU stat (Linux) — `-c %Y`; BSD stat (macOS) — `-f %m`; на Linux `-f` тоже
    # «работает», но печатает статистику файловой системы, поэтому порядок важен.
    [ -n "$ts" ] || ts=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo 0)
    case $ts in '' | *[!0-9]*) ts=0 ;; esac
    if [ "$ts" -gt "$latest_ts" ]; then latest_ts=$ts; latest=$f; fi
done
[ -n "$latest" ] || exit 0

tag=${latest#docs/SFR}; tag=${tag%_REPORT.md}   # 5, 5c, 6, …

# 1) раздел «ревью» в отчёте: заголовок со словом «ревью» и ≥3 непустых строк
#    текста до следующего заголовка того же или более высокого уровня
#    (пустой раздел-заготовка «§12» до ревью не считается). Регистр — без tolower:
#    awk на macOS не приводит кириллицу.
if awk '
    BEGIN { insec = 0; lines = 0; lvl = 0 }
    /^#{1,4} / {
        match($0, /^#+/); n = RLENGTH
        if (insec && n <= lvl) { insec = 0 }
        if (!insec && $0 ~ /[Рр]евью/) { insec = 1; lvl = n; next }
    }
    insec && NF > 0 { lines++ }
    END { exit (lines >= 3) ? 0 : 1 }
' "$latest"; then
    exit 0
fi

# 2) старый след: файл ревью на диске или в истории git.
review="docs/REVIEW_SFR${tag}.md"
[ -e "$review" ] && exit 0
git log --oneline -1 -- "$review" 2>/dev/null | grep -q . && exit 0

# Один показ на сессию: Stop срабатывает в конце каждого турна.
# session_id достаём sed'ом, а не jq: хук не должен зависеть от того,
# установлен ли jq на машине.
session=$(printf '%s' "$payload" |
    sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
stamp="${TMPDIR:-/tmp}/sfr-review-reminder-${session:-nosession}-SFR${tag}"
stamp=${stamp//[^A-Za-z0-9_.\/-]/_}
[ -e "$stamp" ] && exit 0
: >"$stamp" 2>/dev/null || true

# JSON собирается printf: в сообщении нет кавычек и обратных слэшей.
printf '{"systemMessage":"Итерация SFR-%s закрыта (%s), независимого ревью нет: в отчёте нет раздела «ревью». Запусти /review-iteration SFR-%s (субагент sfr-reviewer, можно в этой же сессии) и запиши итог разделом отчёта."}\n' \
    "$tag" "$latest" "$tag"
