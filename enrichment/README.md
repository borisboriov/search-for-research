# Enrichment: явный поиск → источники → Sol → человек

Рабочий модуль контактов Search For Research. Алгоритмы, рубрика и принятые
границы результата сохранены; [карта исследований и хранения](research/INDEX.md)
ведёт к baseline, human record и live3. Код и документы этого переноса пока в
[PR #194](https://github.com/borisboriov/search-for-research/pull/194).

| Часть | Назначение |
|---|---|
| `src/sfr_enrichment/` | Поддерживаемый runtime: loader, literal binding, native verifier, guards, human cards |
| `configs/verifier-v3.md` | Прежняя рубрика, байты не изменены |
| `tests/` | Перенесённые регрессии и проверки границ модуля с заблокированными реальными транспортами |
| `research/methods/`, `research/reports/` | Версионированные методики и результаты прежних этапов |
| `research/legacy/` | Исторические GLM/night/Pi эксперименты; runtime их не импортирует |

## Установка и проверка без сети

Нужен checkout этого репозитория на конкретном Git SHA, Python 3.12+ и `uv`.
Из корня: `uv sync --locked --all-packages --group enrichment`, затем `make unhide`
(для editable imports на macOS). Версии библиотек заданы `uv.lock`, включая
`pypdf==6.19.0`. Изолированного wheel без ресурсов репозитория недостаточно.
Offline повтор установки возможен только при уже заполненном кэше зависимостей.
Команда `uv run sfr-enrichment --help` показывает единый CLI; равнозначен
`.venv/bin/python -m sfr_enrichment`.

После установки один воспроизводимый offline запуск регрессий из корня:

```sh
.venv/bin/python enrichment/tests/run_offline.py
```

Он блокирует реальную сеть и запуски клиентов моделей; локальные Python-процессы
для help и PDF разрешены. Для проверки собственного сохранённого sealed архива:

```sh
.venv/bin/python -m sfr_enrichment archive-check \
  --root "$SFR_ENRICHMENT_ARCHIVE" --index "$SFR_ENRICHMENT_INDEX" \
  --index-sha "$SFR_ENRICHMENT_INDEX_SHA"
```

Все три значения берутся из частного каталога архивов. Для final assisted live3
проверено 219 mapped файлов; полный SHA transfer index начинается `183162a57035`.
Точный индекс, SHA и путь сохранены в архиве, без переименования. Команда читает
данные и не вызывает источники или модели. `saved` дополнительно проверяет
старый baseline и создаёт новый локальный human packet, поэтому требует нового
выходного root. Контракт inputs/scope и команды описаны в
[действующей части методики](research/methods/enrichment_glm_runner.md#sol-assisted-контакты-переносимый-offline-tested-workflow-11102026).

## Будущий live запуск

Для другого компьютера нужны тот же Git SHA/lock, локальные входы, новый частный
абсолютный data-root, действующий доступ native `codex` CLI по подписке и отдельно
доступный поисковый инструмент у Sol-агента. CLI поиска не предоставляет;
запись discovery не заменяет tool receipt. Исторические Pi SDK зависимости не
нужны рабочему пути. Пользователь отдельно задаёт выборку, разрешение, HTTP/model
лимиты, сроки и основание ORCID access. Поиск передаёт локальные profiles.json и
plan.json; scope.json фиксирует это разрешение.

После такого разрешения из корня checkout:

```sh
uv run sfr-enrichment prepare --root "$SFR_ENRICHMENT_DATA_ROOT" \
  --profiles /absolute/profiles.json --plan /absolute/plan.json --scope /absolute/scope.json
uv run sfr-enrichment dry-run --root "$SFR_ENRICHMENT_DATA_ROOT"
# Только для отдельно разрешённого live scope и фактического официального остатка:
uv run sfr-enrichment run --live --root "$SFR_ENRICHMENT_DATA_ROOT" \
  --remaining-percent ACTUAL_OFFICIAL_PERCENT
```

В этом этапе live не запускался. `prepare` замораживает все фактические `.py`
рабочего пакета, lock, packaging и рубрику; wrappers и исторические runners
не входят в новый freeze. Старые manifest/code hashes остаются неизменными:
для исторического code freeze нужен его точный Git SHA и lock, продолжать его
новым кодом нельзя. STOP/unknown attempt запрещают повтор. Ограничения sources,
robots, deadlines и полноты сохраняются; provenance не выдаёт requested модель
за фактически подтверждённую.

## Совместимость и хранение

Прежние Python entrypoints в `scripts/enrichment_*.py` — тонкие адаптеры к новым
модулям. Для извлечённых helpers compatibility adapter сохраняет старые
patch targets общих helpers и передаёт их подмены фактическим runtime globals;
различающиеся исторические функции остаются отдельными. Проверяются все
87 прежних строковых targets, включая native/source transports и восстановление. JS-адаптеры ведут в
`research/legacy/js/`. Исторические команды относятся к прежнему протоколу;
старый sealed live root возобновляют только его точной исторической версией.

Новый рабочий путь сохраняет один `events.jsonl` native verifier, полный raw/result,
receipt, request, usage, ошибки и timeout. Pi-клиент с отдельным полным snapshot
на каждый token delta не импортируется. Это устранение источника будущего
раздувания без сжатия; hard cap всего native event stream не введён. Источники и
производные сохраняются полностью в действующих лимитах (8 MiB PDF, 2 MiB другие
ответы), общий размер run не обещан заранее.

Частные данные, raw, human answers, STOP и seals не входят в git. Старые архивы
сейчас объединены ссылками в каталоге: ни перемещения, ни удаления, ни сжатия,
ни освобождённого места. Для будущих запусков предлагается один внешний
`SFR_ENRICHMENT_DATA_ROOT` с отдельным root на разрешённый run; прежние каталоги
остаются адресуемыми оригиналами.
