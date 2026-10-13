# Offline components — #198, часть A

Минимальный исследовательский replay; поддерживаемый live runtime не меняется.
Только сохранённые 25 источников frozen10, ссылки вместо копирования корпусов.
Новый private root не должен существовать до freeze. Rules и SHA скрипта
фиксируются до результатов. Replay не читает human baseline; evaluate читает
его отдельно после извлечения. Поля candidates и automatic_accepted различаются:
извлечение само по себе не доказывает принадлежность, дату или current.

Из корня checkout, в новой отдельной среде (Python 3.12):

```sh
uv venv --python 3.12 "$COMPONENT_ENV"
uv pip install --python "$COMPONENT_ENV/bin/python" --require-hashes \
  -r enrichment/research/components/requirements.lock
# macOS: очистить hidden flags для корректной загрузки библиотек.
chflags -R nohidden "$COMPONENT_ENV"  # только macOS
export COMPONENT_PYTHON="$COMPONENT_ENV/bin/python"
```

Replay в этой среде:

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

После evaluate можно экспортировать допустимые агрегаты без контактов:

```sh
"$COMPONENT_PYTHON" enrichment/research/components/export_summary.py \
  --root "$NEW_PRIVATE_ROOT" --output /absolute/new-summary.json
```

`findyourprofessor` здесь означает только `extract_emails` на raw HTML; полный
scraper и его keyword filtering/обход не проверяются. Основной контроль использует
текущий HTML extractor и ContactsHTML, а не полный семантический baseline10.
Преобразование пробелов около `@`, OCR и Math-Net rendering не входят в правила.
Границы и выводы — [отчёт #198](../reports/free_components198_20261013.md).

## Один дополнительный post-observation вариант

Готовые проектные renderer и правило пробелов, без произвольного JS/сети:

```sh
"$COMPONENT_PYTHON" enrichment/research/components/adapted_control.py freeze \
  --baseline "$BASELINE_ROOT" --root "$ADAPTED_PRIVATE_ROOT"
"$COMPONENT_PYTHON" enrichment/research/components/adapted_control.py replay \
  --root "$ADAPTED_PRIVATE_ROOT"
"$COMPONENT_PYTHON" enrichment/research/components/adapted_control.py evaluate \
  --root "$ADAPTED_PRIVATE_ROOT" --human "$HUMAN_RECORD"
"$COMPONENT_PYTHON" enrichment/research/components/bind_entity_quotes.py \
  --root "$ADAPTED_PRIVATE_ROOT" --prefix final-
"$COMPONENT_PYTHON" enrichment/research/components/export_summary.py \
  --root "$ADAPTED_PRIVATE_ROOT" --output /absolute/new-adapted-summary.json
```

Новый root обязателен; adapter/rules и существующие decoder receipts фиксируются
до replay. Entity binding только связывает уже извлечённые значения с исходной
строкой через stdlib html.unescape, не добавляет email. Старый run-v2 повторять
на его frozen checkout `fabb991e61390c5aeaae1d42c56a4a35f6b928be`; новый helper
меняет runtime SHA, хотя unadapted extraction правила/результат прежние.

Исправление provenance уже сохранённого адаптированного replay без extraction:

```sh
"$COMPONENT_PYTHON" enrichment/research/components/adapted_control.py bind \
  --root "$ADAPTED_PRIVATE_ROOT" --prefix corrected-
"$COMPONENT_PYTHON" enrichment/research/components/bind_entity_quotes.py \
  --root "$ADAPTED_PRIVATE_ROOT" --input-prefix corrected- --prefix corrected-
```

Точные CRLF сохраняются через bytes.decode(); offsets — позиции символов исходного
decoded UTF-8 представления, SHA — байтов файла. Старые binding-файлы не меняются.
При свежем replay исправленный binder вызывается автоматически. Единственный
сохранённый extraction в новом root относится к frozen adapter на `b929c4b`;
исправление только provenance использует последующий head, не новый эксперимент.
