#!/usr/bin/env bash
# Выкладка кода на VPS одной командой: `make deploy` (с 28.09.2026).
# Это процедура «Обновление» из deploy/README.md, запущенная с машины разработчика:
#   1. показать, что уедет: коммит на сервере и коммиты origin/main сверх него;
#   2. спросить подтверждение — только с терминала (/dev/tty);
#   3. на сервере: git pull --ff-only → docker compose up -d --build → дождаться
#      сайта → ревалидация ISR → проверки (лендинг, sitemap до и после, контейнеры).
# Артефакты (индекс, cards) не возит: это deploy/sync-artifacts.sh и чеклист
# «Смена индекса» в README — у смены индекса другой порядок шагов.
#
# Выкладка — только Борис (CLAUDE.md). Агенту `make deploy` и этот скрипт
# отклоняет хук .claude/hooks/block-push.sh; подтверждение с /dev/tty — второй
# предохранитель: у сессии Claude Code терминала нет.
#
# Адрес сервера — deploy/target.local (VPS_HOST, VPS_USER; в git не попадает).
# Каталог репозитория на сервере — SFR_REMOTE_DIR (по умолчанию search-for-research).
set -euo pipefail

cd "$(dirname "$0")/.."

target=deploy/target.local
if [[ ! -f $target ]]; then
    echo "нет $target — в нём адрес сервера (VPS_HOST, VPS_USER); в git не попадает" >&2
    exit 1
fi
# shellcheck source=/dev/null
source "$target"
: "${VPS_HOST:?в deploy/target.local нет VPS_HOST}" "${VPS_USER:?в deploy/target.local нет VPS_USER}"
host="$VPS_USER@$VPS_HOST"
remote_dir=${SFR_REMOTE_DIR:-search-for-research}

echo "→ $host:$remote_dir"
# Скрипт для сервера идёт через stdin (bash -s): у команд внутри stdin — /dev/null,
# иначе они дочитали бы остаток скрипта.
ssh "$host" bash -s -- "$remote_dir" <<'REMOTE'
set -euo pipefail
cd "$1"
git fetch -q origin main </dev/null
echo "сейчас на сервере: $(git log --oneline -1 HEAD)"
dirty=$(git status --porcelain --untracked-files=no)
if [[ -n $dirty ]]; then
    echo "ВНИМАНИЕ: на сервере правлены отслеживаемые файлы — pull может не пройти:"
    echo "$dirty"
fi
pending=$(git log --oneline HEAD..origin/main)
if [[ -n $pending ]]; then
    echo "уедет:"
    echo "$pending"
else
    echo "новых коммитов нет — пересборка всё равно подтянет патчи базовых образов"
fi
REMOTE

if ! read -r -p "Выкладываю на прод? [y/N] " answer </dev/tty; then
    echo "нет терминала: make deploy запускает Борис из своего терминала" >&2
    exit 1
fi
case $answer in
    y | Y | yes | д | Д | да) ;;
    *)
        echo "отменено"
        exit 1
        ;;
esac

ssh "$host" bash -s -- "$remote_dir" <<'REMOTE'
set -euo pipefail
cd "$1"
# Переменные нужны только этому скрипту (адрес, секрет ревалидации): без export,
# compose по-прежнему читает deploy/.env сам.
# shellcheck source=/dev/null
source deploy/.env
: "${NEXT_PUBLIC_SITE_URL:?в deploy/.env нет NEXT_PUBLIC_SITE_URL}"
: "${REVALIDATE_SECRET:?в deploy/.env нет REVALIDATE_SECRET}"
domain=${NEXT_PUBLIC_SITE_URL#https://}

sitemap_count() {
    curl -s -m 30 "https://$domain/sitemap.xml" </dev/null | grep -c '/supervisor/' || true
}

before=$(git rev-parse --short HEAD)
profiles_before=$(sitemap_count)
git pull --ff-only -q </dev/null
after=$(git rev-parse --short HEAD)
echo "код: $before → $after (точка отката — $before)"

cd deploy
docker compose up -d --build </dev/null

echo "жду https://$domain/ …"
up=0
for _ in $(seq 1 90); do
    if curl -sf -o /dev/null -m 10 "https://$domain/" </dev/null; then
        up=1
        break
    fi
    sleep 2
done
if [[ $up -ne 1 ]]; then
    echo "сайт не ответил за 3 минуты — смотри docker compose logs --tail=50 web proxy" >&2
    docker compose ps </dev/null
    exit 1
fi

# Сборка web шла без живого API: без ревалидации лендинг и sitemap отдают
# деградированный снапшот (deploy/README.md, «Обновление»).
if curl -sf -m 30 -X POST -H "x-revalidate-secret: $REVALIDATE_SECRET" \
    "https://$domain/api/revalidate" </dev/null; then
    echo
else
    echo "ревалидация не прошла — повтори curl из deploy/README.md («Обновление»)" >&2
fi

profiles_after=$(sitemap_count)
echo "лендинг: HTTP $(curl -s -o /dev/null -m 10 -w '%{http_code}' "https://$domain/" </dev/null)"
echo "sitemap: $profiles_before → $profiles_after профилей"
if [[ $profiles_after != "$profiles_before" ]]; then
    echo "ВНИМАНИЕ: число профилей в sitemap изменилось — без смены индекса так быть не должно" >&2
fi
docker compose ps </dev/null
echo "готово: $after на https://$domain"
REMOTE
