#!/usr/bin/env bash
# Обновление вендоренных правил semgrep (SFR-4b).
#
# Правила реестра semgrep.dev не версионируются: `--config p/python` каждый раз
# отдаёт «сегодняшний» набор, то есть аудит невоспроизводим, а CI ходит в
# внешний сервис на каждом прогоне. Поэтому паки выгружены в репозиторий один
# раз; `make audit` и CI-job security читают их с диска и работают офлайн.
#
# Обновлять — осознанно: запустить скрипт, посмотреть diff правил, прогнать
# `make audit`, разобрать новые находки, зафиксировать дату ниже и в
# docs/SECURITY_CI.md.
#
# Использование:  bash security/semgrep/fetch-rules.sh
set -euo pipefail

cd "$(dirname "$0")"

# Чего здесь намеренно нет:
#   p/nextjs — реестр отдаёт пустой набор (`rules: []`, 0 правил);
#             замена — p/react (docs/DECISIONS.md);
#   p/secrets — файл правил целиком состоит из секрето-подобных строк
#             (регулярки и плейсхолдеры вида hooks.slack.com/services/T0000…).
#             Его нельзя держать в репозитории: GitHub Push Protection
#             отклоняет пуш, а наш же gitleaks помечает файл как утечку.
#             Слой секретов закрыт gitleaks — рабочее дерево и вся история.
PACKS="python typescript docker react"

for p in $PACKS; do
    echo "→ p/$p"
    curl -sS --fail -L "https://semgrep.dev/c/p/$p" -o "$p.yaml"
    printf '   %s правил\n' "$(grep -c '^- id:' "$p.yaml")"
done

{
    echo "# Выгружено security/semgrep/fetch-rules.sh"
    echo "# Дата выгрузки: $(date -u +%Y-%m-%d)"
    echo "# Источник: https://semgrep.dev/c/p/<pack>"
    for p in $PACKS; do
        printf '%s  %s.yaml  (%s правил)\n' \
            "$(shasum -a 256 "$p.yaml" | cut -d' ' -f1)" "$p" "$(grep -c '^- id:' "$p.yaml")"
    done
} > MANIFEST.txt

cat MANIFEST.txt
