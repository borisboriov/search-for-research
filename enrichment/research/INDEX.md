# Карта enrichment: методы, результаты и частные архивы

Вход и команды — [README модуля](../README.md). Источник чисел этой карты —
[storage-audit.json](storage-audit.json), полученный из частного read-only каталога
11.10.2026; показатели качества остаются в прежних артефактах измерений.

## Три результата, которые нужно находить первыми

| Результат | Где читать | Частный оригинал и сохранность |
|---|---|---|
| Sol-assisted baseline10: 8 личных контактов | [Отчёт baseline](reports/enrichment_night_20261009.md#sol-assisted-workflow-и-baseline-contact-cards--11102026) | `enrichment-flexible10-20261010`: 865 mapped файлов проверены; классификации 10 профилей совпали |
| Реальные human-v3 ответы Бориса на 8 контактов | [Отчёт и границы human](reports/enrichment_night_20261009.md#sol-assisted-live3-и-четыре-человеческих-вопроса--11102026) | `enrichment-human-baseline-contacts-20261011`: record SHA сохранён, копия в compatibility replay совпала байтами |
| Final Sol-assisted live3: 3/3 сквозных запуска, 2 личных контакта | [Live3 и ограничения](reports/enrichment_night_20261009.md#sol-assisted-live3-и-четыре-человеческих-вопроса--11102026) | `enrichment-sol-assisted-live3-20261011`: 219 mapped файлов проверены, повторная классификация 3 профилей совпала |

Точные абсолютные пути этих трёх результатов и всех охваченных архивов находятся
в одном частном artifact-catalogue.json нового root
`enrichment-module-storage-20261011` рядом с прежними enrichment экспериментами.
Каталог содержит назначение через категории, counts/bytes, ошибки доступа,
retention и key_results; источники/PII он не читает и не публикует. Его собственный
root исключён из исторической переписи. Полное offline доказательство лежит
рядом как `offline-equivalence.json`: 17 прежних index SHA и 2468 mapped файлов
в четырёх ключевых roots. Исторические transfer indices не перезаписаны.

## Бесплатные компоненты — #198, часть A

[Offline comparison frozen10, 13.10.2026](reports/free_components198_20261013.md):
25 сохранённых источников; обычные HTML/PDF extractor восстановили 5/8 известных
human-контактов без предобработки; отдельный post-observation контроль с готовыми
проектными обработчиками восстановил 8/8 для control/bs4 + PDF, 7/8 для
Trafilatura/FYP + PDF. [Новые агрегаты](reports/free_components198_adapted_metrics.json).
Принадлежность требует отдельной проверки; source HTTP/model
inference 0. [Агрегаты](reports/free_components198_metrics.json) получены из private
run, источники/ответы не опубликованы. Новый root `enrichment-free198-20261013`;
старые архивы не менялись. Ветка/ревью/CI — [PR #200](https://github.com/borisboriov/search-for-research/pull/200),
PR #200 влит 13.10.2026; часть B Яндекс ожидает отдельного разрешения.

## Рабочий путь и новая пятёрка — #202

[Отчёт интеграции, 13.10.2026](reports/runtime202_20261013.md),
[агрегаты](reports/runtime202_metrics.json): пять новых каталожных профилей из пяти
организаций, семь пригодных источников, четыре кандидата old/new, три личных
контакта по Sol без установленной актуальности, один отклонённый общий ящик.
15 search queries, 13 физических source HTTP, шесть native attempts включая
неудачный startup; human_reviewed=0. Все 404 model-visible spans/SHA проверены.
Прироста извлечения на этой пятёрке нет; новизна ограничена проверенными
метаданными старых runs, это не holdout. Частный root
`enrichment-runtime202-20261013` сохраняет тела/receipts/карточки/STOP и отказы.
[PR #204](https://github.com/borisboriov/search-for-research/pull/204) влит 13.10.2026;
старые данные и human record не изменялись.

## Три пропуска после новой пятёрки — #205

[Диагностика и альтернативы](reports/misses205_20261013.md),
[агрегаты](reports/misses205_metrics.json): на тех же трёх трудных случаях
получены три личных email по Sol у двух людей (Киселев1historical, Кузнецов2undated),
Горин в пределах поиска без email. Новых human оценок0; актуальность/readiness
неизвестны. Изменились источники, extractor из влитого #204 не менялся;
ошибка выбора одноимённого автора исправлена, общие/чужие адреса отклонены.
16search/15physicalsourceHTTP/4native jobs,385spans проверены; private root
`enrichment-misses205-20261013` хранит отказы, тела, карточки иSTOP.
[PR206](https://github.com/borisboriov/search-for-research/pull/206) влит 14.10.2026.
Это не holdout и не общая оценка качества/экономики каталога.

## Заключительная новая десятка — #207

[Отчёт partial, 14.10.2026](reports/final207_20261014.md),
[агрегаты](reports/final207_metrics.json): frozen10 из десяти каталожных организаций,
155 известных IDs исключены по ограниченным метаданным; не blind holdout.
30 search queries, 2 физических source HTTP, 0 native jobs. Первый smoke
остановился на ConnectError robots.txt КФУ после полного ORCID200; остальные
9 не начаты по заранее заданному правилу. Контактное покрытие, качество и полная
воспроизводимость не измерены. Runtime/рубрика неизменны, retries 0, STOP сохранён.
Private root `enrichment-final207-20261014`; [PR208](https://github.com/borisboriov/search-for-research/pull/208)
влит 14.10.2026 (`6038766a34ff06afae3beb9690c62d98884d31da`). Повтор тех же профилей — #209 ниже; новая выборка не запускается.

## До и после переноса

| До | Теперь | Граница |
|---|---|---|
| 28 Python enrichment файлов в общих `scripts/` | Рабочий пакет `src/sfr_enrichment/`, исторические модули `research/legacy/`, тонкие старые wrappers | Рабочий CLI не импортирует GLM/night/Pi orchestration |
| 23 Python теста и 3 JS теста рядом со скриптами | `tests/` и `research/legacy/js/`; общие проверки подключены через Makefile | Offline guard запрещает реальные transports |
| Методики и отчёты в общих `docs/experiments`, `docs/reports` | `methods/`, `reports/`, рубрика `../configs/` | Метрики в `docs/metrics` и значения замороженных результатов сохранены |
| Список старых script hashes | Freeze всех фактических файлов runtime + packaging/lock/rubric | Исторические freezes проверяют исторический checkout |
| Разрозненные частные roots | Единый каталог ссылок; для новых runs внешний data-root | Старые bytes/paths/STOP остаются на месте |

## Что занимает место

В 44 каталогах enrichment: **216235 файлов, 12521097118 logical bytes**
(12,52 GB / 11,66 GiB), **12977324032 allocated bytes**. Pi snapshots:
**199863 файла, 11633708957 logical bytes**, около 92,9% объёма. Категория source bodies
по именам файлов: 462 файла / 50683188 bytes; это нижняя граница, некоторые
старые источники включены в `other`. Категории — эвристика путей, не полный
content audit. Более широкий независимый source census дал 2339 файлов /
455956640 bytes (~3,6%); методы группировки отличаются. Repeat3 один занимает
7169179242 bytes, из них Pi events 7141860029 bytes.

Причина подтверждена на малых сохранённых событиях: subscribe старого Pi runner
писал целиком каждый event, включающий растущие partial и message. У события
`013065-session-event.json` из repeat3 delta — 9 символов; обе копии content
равны, весь файл — 131055 bytes. 26118 таких событий в одном run дают повтор
накопленного текста. Сохранение только delta не обеспечивает точного replay:
на соседней паре другая delta не реконструировала следующий snapshot. Источники
нельзя объявить мусором: raw/decoded/text нужны для буквальных SHA, parser replay,
robots/error и human provenance.

В поддерживаемом CLI Pi исключён; native сохраняет поток в один JSONL без
отдельных cumulative snapshot файлов. Synthetic 100-event fixture проверяет
байтовую сохранность raw/events, usage, receipt и ошибку/timeout без нового job.
Сжатие не выбрано. В рабочем assisted verifier #202 stdout/events и stderr
ограничены 16 MiB каждый; переполнение завершает job без повтора. Опциональный
`scope.disk_byte_cap` проверяет бюджет перед HTTP/native; #202 задаёт 128 MiB.
Time/source/request caps и лимит каждого потока учитываются отдельно.

Более широкий ограниченный census: **77 путей, 387467 уникальных файлов,
38083866465 logical / 39016140800 allocated bytes**. Это контекст SFR, включая
общий основной checkout (~23,85 GB), его dependencies/data и worktrees;
эти байты не приписываются enrichment. Downloads недоступен (`PermissionError`),
домашняя папка проверена только по совпадающим верхнеуровневым именам.
Симлинки не обходились, hardlinks считались по dev/inode; APFS clone extents
не измерены, allocated не доказывает физическое освобождение при удалении.

## Каталог исторических enrichment roots

Ниже исходные имена и измеренные размеры; точные пути, категории и ошибки —
в частном каталоге. Каждый root сохраняется логическим архивом на прежнем месте.
Этапы методов объясняют [методики](methods/enrichment_glm_runner.md), накопленные
измерения — [основной отчёт](reports/enrichment_night_20261009.md).

| Имя архива | Файлы | Logical bytes | Allocated bytes |
|---|---:|---:|---:|
| `enrichment-contact-first-20261010` | 193 | 1486882 | 2019328 |
| `enrichment-contact-first-authorized-20261010` | 110 | 263394 | 638976 |
| `enrichment-contact-first-authorized-retry-20261010` | 139 | 694873 | 1159168 |
| `enrichment-contact-first-exact-links-20261010` | 185 | 543922 | 1163264 |
| `enrichment-contact-first-fresh-20261010` | 10 | 64034 | 90112 |
| `enrichment-flexible10-20261010` | 866 | 41788385 | 44367872 |
| `enrichment-fragment-offline3-20261011` | 12685 | 678888146 | 704659456 |
| `enrichment-fragment-repeat3-20261011` | 69218 | 7169179242 | 7311093760 |
| `enrichment-glm-remaining6-20261011` | 1317 | 15589579 | 19976192 |
| `enrichment-glm-remaining8-20261011` | 533 | 8991300 | 10612736 |
| `enrichment-glm-runner-live10-20261010` | 606 | 18655885 | 20439040 |
| `enrichment-glm-runner-preflight-20261010` | 107 | 1582333 | 1867776 |
| `enrichment-gpt-compact-v1-20261009` | 10 | 60987 | 81920 |
| `enrichment-gpt-compact-v1-fixed-20261009` | 146 | 1264376 | 1634304 |
| `enrichment-human-baseline-contacts-20261011` | 1 | 333083 | 335872 |
| `enrichment-live3-independent-sol-20261011` | 656 | 13976233 | 16080896 |
| `enrichment-live3-partial-offline-20261011` | 78 | 4268771 | 4456448 |
| `enrichment-night-cli-v1-20261009` | 102 | 231601 | 532480 |
| `enrichment-night-cli-v2-20261009` | 243 | 23483409 | 24309760 |
| `enrichment-night-cli-v3-20261009` | 241 | 537864 | 1355776 |
| `enrichment-night-cli-v3-fixed-20261009` | 873 | 2298842 | 5353472 |
| `enrichment-night-cli-v4-20261009` | 1904 | 21013698 | 27504640 |
| `enrichment-night-direct-http-canonical-20261010` | 37 | 266011 | 364544 |
| `enrichment-night-direct-http-control-20261010` | 35 | 132890 | 233472 |
| `enrichment-night-early-read-v6-control-20261010` | 6 | 17064 | 32768 |
| `enrichment-night-early-read-v6-paired-20261010` | 528 | 1336116 | 3137536 |
| `enrichment-night-literal-format-v5-fresh-20261010` | 493 | 650862 | 2392064 |
| `enrichment-night-literal-format-v5-replay-20261010` | 17 | 126468 | 163840 |
| `enrichment-night-literal-format-v5-replay-fixed-20261010` | 208 | 1410492 | 1994752 |
| `enrichment-night-url-control-20261010` | 79 | 186065 | 438272 |
| `enrichment-observed-links-hse-20261010` | 38 | 168370 | 278528 |
| `enrichment-orcid-date-offline6-20261011` | 120 | 7925946 | 8237056 |
| `enrichment-pi12-20261009` | 57084 | 546558254 | 663650304 |
| `enrichment-pi12-high-20261009` | 21459 | 494853912 | 538619904 |
| `enrichment-pipeline-handoff-20261011` | 46 | 379899 | 516096 |
| `enrichment-publication-control1-20261011` | 348 | 4389237 | 5492736 |
| `enrichment-search-contract-offline-20261010` | 24 | 137723 | 200704 |
| `enrichment-sol-assisted-live3-20261011` | 220 | 11824746 | 12443648 |
| `enrichment-sol-assisted-offline-20261011` | 69 | 4073631 | 4255744 |
| `enrichment-validated-redirect-hse-20261010` | 45 | 1905862 | 2052096 |
| `enrichment-verifier-benchmark-20261009` | 51 | 10726950 | 10846208 |
| `enrichment-verifier-pair-20261009` | 15151 | 1031448293 | 1062633472 |
| `enrichment-verifier-three-20261009` | 27553 | 1815390088 | 1872089088 |
| `enrichment100-20261008` | 2401 | 581991400 | 587517952 |

## Критичность и будущая уборка

| Тип | Зачем нужен | Действие сейчас / будущая возможность |
|---|---|---|
| Seals, manifests, STOP, frozen code/parser, raw/final outputs, human records | Проверяемость выводов и неизменность решений | Сохранить оригиналы; физическая консолидация только отдельным планом с индексами и replay |
| Полные источники и производные | Литеральные spans, source binding, PDF/date guards | Сохранить; точный меж-run dedup возможен после отдельной проверки ссылок/SHA |
| Pi cumulative snapshots | Историческая последовательность и отказы | Сохранить без сжатия; будущий рабочий путь их не создаёт |
| `.venv`, `node_modules`, caches | Регенерируемая среда, но cache иногда нужен историческому replay | Возможные кандидаты на отдельную уборку после проверки lock/доступности; сейчас не удалены |
| Методики, отчёты, fixtures, агрегаты | Объяснение протоколов и измерений | Версионировать вместе с кодом; не дублировать raw в git |

Сейчас освобождено **0 bytes**. План физического объединения: сначала сверить
SHA и права, выбрать единственный оригинал, проверить parser/replay и ссылки
старых manifests, затем получить отдельное разрешение переноса/удаления.
Архивировать в этом раунде означает каталогизировать. Сжатия и копирования
старых гигабайт не было. Новых source/search/profile jobs и human answers — 0;
накопленный счётчик profile jobs остаётся 46. Предыдущие метрики актуальности,
доставляемости и покрытия не повышаются результатом реорганизации.

- [Изоляция ошибок источников #209, 14.10.2026](reports/isolation209_20261014.md) — PR #210: один профиль завершён, второй остановлен guard 1 MB, восемь не запущены; frozen meter failed, post-hoc диагностика раскрыта. [Агрегаты](reports/isolation209_metrics.json).

- [Lossless вход и все десять исходов #209, 14.10.2026](reports/compact209_20261014.md) — продолжение в PR210:6date-gated (1inherited),2oversized,2invaliddate; frozenR3meterPASS,7newjobs/29HTTP/0search. [Агрегаты](reports/compact209_metrics.json).
