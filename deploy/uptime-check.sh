#!/usr/bin/env bash
# Простой uptime-чек с самого сервера (SFR-4 §2): статус сайта по HTTP и
# здоровье контейнеров по docker healthcheck (API снаружи compose недоступен —
# это дизайн, поэтому его прямой URL проверить нельзя и не нужно).
#
# Крон (внешний uptime-сервис — на Борисе):
#   */5 * * * * /home/USER/search-for-research/deploy/uptime-check.sh https://search-for-research.ru >> $HOME/uptime.log 2>&1
set -u

ts=$(date -u +%FT%TZ)
site=${1:-http://localhost:8080}

code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$site/") || code=000
echo "$ts GET $site/ -> $code"

for name in sfr-api sfr-web sfr-proxy; do
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$name" 2>/dev/null) || health=absent
    echo "$ts container $name -> $health"
done
