# Offline components — #198, часть A

Минимальный исследовательский replay; поддерживаемый live runtime не меняется.
Только сохранённые 25 источников frozen10, ссылки вместо копирования корпусов.
Новый private root не должен существовать до freeze. Rules и SHA скрипта
фиксируются до результатов. Replay не читает human baseline; evaluate читает
его отдельно после извлечения. Поля candidates и automatic_accepted различаются:
извлечение само по себе не доказывает принадлежность, дату или current.

Из корня checkout, в отдельной среде с зависимостями `requirements.lock`:

```sh
export PYTHONPATH="$PWD/enrichment/src"
"$COMPONENT_PYTHON" enrichment/research/components/offline_components.py freeze \
  --baseline "$BASELINE_ROOT" --root "$NEW_PRIVATE_ROOT"
"$COMPONENT_PYTHON" enrichment/research/components/offline_components.py replay \
  --root "$NEW_PRIVATE_ROOT"
"$COMPONENT_PYTHON" enrichment/research/components/offline_components.py evaluate \
  --root "$NEW_PRIVATE_ROOT" --human "$HUMAN_RECORD"
```

Точные private paths — artifact-catalogue.json, описанный в [INDEX](../INDEX.md).
Manifest, replay и evaluation записываются один раз; повтор — в новом root.
В Git не сохранять email, raw bodies и human record. HTTP источников и новых
профильных модельных jobs — 0. Установка пакетов/проверки разработки учитываются
отдельно. Макет правил предназначен для диагностики знакомой выборки; это
не blind и не оценка распространённости контактов в каталоге.
