#!/usr/bin/env bash
# Условное Stop-напоминание при незакоммиченных изменениях.
# Не определяет авторство, готовность PR или намерение завершить работу.
# Не запускает проверки и не хранит состояние; актуальность PR проверяет handoff.
set -uo pipefail

payload=$(cat 2>/dev/null || true)
if printf '%s' "$payload" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
    exit 0
fi
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$root" || exit 0
changes=$(GIT_OPTIONAL_LOCKS=0 git status --porcelain --untracked-files=normal 2>/dev/null) || exit 0
[ -n "$changes" ] || exit 0

printf '%s\n' '{"systemMessage":"В рабочей папке есть изменения. Если сейчас передаёте свой результат, завершите применимый маршрут из AGENTS: обновите основной материал и проверьте его источники; для PR нужны актуальные независимое ревью, CI и handoff. Это напоминание не устанавливает отсутствие ревью и не требует нового отчёта, аудита обсуждения или изменений чужой работы."}'
