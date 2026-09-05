#!/usr/bin/env bash
# Доставка артефактов на VPS (SFR-4 §1): индекс и обогащение карточек
# собираются офлайн (make index-sfr2, make export-cards) и привозятся —
# на сервере ничего не собирается. Веса FRIDA скрипт не возит: их скачает
# первый старт контейнера в том hf-cache (~2 ГБ, единожды).
#
# Запуск из корня репозитория:
#   deploy/sync-artifacts.sh user@vps-host [путь-к-репо-на-сервере]
#
# rsync -c сверяет чексуммы: повторный запуск ничего не передаёт, если
# артефакты не менялись.
set -euo pipefail

HOST=${1:?использование: deploy/sync-artifacts.sh user@host [remote_dir]}
REMOTE_DIR=${2:-search-for-research}

for path in data/indexes_sfr2/frida_clean/meta.json data/exports/cards.jsonl; do
    if [[ ! -f $path ]]; then
        echo "нет $path — собери артефакты: make index-sfr2 / make export-cards" >&2
        exit 1
    fi
done

rsync -avc --delete data/indexes_sfr2/ "$HOST:$REMOTE_DIR/data/indexes_sfr2/"
rsync -avc data/exports/cards.jsonl "$HOST:$REMOTE_DIR/data/exports/cards.jsonl"

echo "готово: индекс и cards.jsonl на $HOST:$REMOTE_DIR"
