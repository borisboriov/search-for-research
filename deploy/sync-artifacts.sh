#!/usr/bin/env bash
# Доставка артефактов на VPS (SFR-4 §1): индекс и обогащение карточек
# собираются офлайн (make index-sfr5c, make export-sfr5c) и привозятся —
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

for path in data/indexes_sfr5c/frida_clean/meta.json data/exports/cards_sfr5c.jsonl; do
    if [[ ! -f $path ]]; then
        echo "нет $path — собери артефакты: make index-sfr5c / make export-sfr5c" >&2
        exit 1
    fi
done

# data/ в git не попадает, поэтому в свежем клоне на сервере его нет, а rsync
# родительские каталоги не создаёт (поймано на первой боевой выкладке 08.09).
ssh "$HOST" "mkdir -p '$REMOTE_DIR/data/indexes_sfr5c' '$REMOTE_DIR/data/exports'"

rsync -avc --delete data/indexes_sfr5c/ "$HOST:$REMOTE_DIR/data/indexes_sfr5c/"
rsync -avc data/exports/cards_sfr5c.jsonl "$HOST:$REMOTE_DIR/data/exports/cards_sfr5c.jsonl"

echo "готово: индекс и cards_sfr5c.jsonl на $HOST:$REMOTE_DIR"
