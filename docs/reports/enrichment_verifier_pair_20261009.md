# Одна пара проверяющих на сохранённом профиле, 09.10.2026

Узкое продолжение [PR #194](https://github.com/borisboriov/search-for-research/pull/194), [постановка](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6084203523), issue #193. Исходный head `5052b017317c5b92f4601ec92d16c15c35b4cf1c`, ветка `codex/enrichment100-20261008`, worktree `/private/tmp/sfr-enrichment100-20261008`. PR проверен OPEN/draft на этой ветке/head, дерево было чистым; профильных enrichment/exec-процессов предыдущего этапа не обнаружено, предыдущая запись прекращена по передаче и итоговому комментарию PR.

**Минимальный запуск работает:** один профиль `A5015573260`, четыре сохранённых атома, два отдельных последовательных задания, одна пригодная пара. Sol запущен первым; Pi получил задание только после пригодного Sol. По одной реальной попытке каждой модели, без второго inference. Оба ответа прошли проверку схемы, идентификаторов задания, полного набора атомов, ссылок и семантического контракта. Это структурная пригодность, не доказанная истинность оценок.

## Передача задания и ограничения клиентов

Sol получает общую инструкцию через поддерживаемый session-local `developer_instructions`. Переопределение `model_instructions_file` убрано: обязательные системные инструкции не подменяются. Инструкция, схема и байты входа скопированы из остановленного root без изменений. Точный общий user prompt содержит задачу и схему; Codex также получает её через `--output-schema`. Offline `debug prompt-input` подтверждает всю общую инструкцию в developer-сообщении и точный последний user-вход. `--strict-config` реального exec принял настройки. Равенство полного списка сообщений Pi/Codex больше не требуется; повреждённый вход или недоставленная инструкция по-прежнему блокируют запуск.

Codex 0.161.0 использует новый `exec --ephemeral`, не resume/fork; нет истории разработчика, старых вердиктов или ответа Pi. Пустой cwd, `project_doc_max_bytes=0`, отключённые веб, MCP, shell/unified_exec, browser/computer use, apps/plugins, multi-agent и code-mode host; sandbox read-only. Общая инструкция запрещает инструменты, команды, чтение иных файлов и веб. Pi 1.1.0 использует новую in-memory сессию без context files/skills/extensions, `tools=[]`; перед публичным SDK stream граница проецирует только общую инструкцию и один точный user prompt. Его callable/active inventory пуст, automatic/provider retries отключены, timeout 600 000 мс.

В Codex render пять сообщений. Вместе с общей инструкцией идут обязательные сведения о навыках, доступе и режиме; ещё два developer-сообщения задают служебные роли, дополнительное user-сообщение содержит домашние Git-правила и environment. В них нет прежних ответов/вердиктов; правила Git не относятся к фактам, сведения о навыках/ролях могут влиять на поведение. Фактически оба агента завершили задание без инструментов. Полные сообщения и их SHA сохранены частно. Отсутствие API base/system или отдельного tool inventory в render **не считается доказательством их отсутствия**. Список tools Codex на wire и точный backend runtime не раскрыты. Причинное влияние служебных сообщений на решения одним запуском не установлено; клиентские контексты и токенизаторы различаются.

Первый postflight guard ошибочно отверг завершённый Sol из-за клиентского pre-turn `item.completed/error`: Code Mode недоступен, потому что host отключён и работает fail-closed. Исправлено распознавание только этого точного предупреждения до `turn.started`; неизвестные события и такое же предупреждение после начала хода отвергаются. Сохранённый raw принят без нового запуска. Первоначальный отказ, frozen адаптер, исправленный postflight и окончательная проверка сохранены раздельно; SHA raw и events до/после recovery совпали. Задание моделей при исправлении не менялось.

В журнале Sol — thread.started, предупреждение клиента, turn.started, agent_message, turn.completed; инструментальных событий нет. Pi: один guarded model request, один завершённый assistant, toolCalls/toolResults = 0; проверены toolCall, toolResult, tool_execution и source reservations в фактических событиях. Запросов сохранённых источников/ORCID или нового веб-сбора — 0. Программная загрузка конфигурации/подписочной авторизации клиентами не является чтением источников проверяющими.

## Ответы, измерения и расхождения

Источник чисел — [агрегаты из исходных receipts](enrichment_verifier_pair_20261009.metrics.json), частный `measurements-final.json`. Backend model/effort не раскрыты обоими провайдерами; не приписываем им requested-настройки. Codex command: requested `openai/gpt-6.1-sol/high`. Pi: requested и SDK-effective `zai/glm-5.3-flash/high`, проверены перед stream. Деньги и дельта подписочной квоты — null; каталожная стоимость Pi не платёж.

| Измерение | Sol | GLM |
|---|---:|---:|
| Реальные задания / пригодные ответы | 1 / 1 | 1 / 1 |
| Время задания, с | 73,277 | 257,990 |
| Input | 16 427 | 3 857 |
| Output, включая reasoning | 2 376 | 15 050 |
| Из них reasoning | 672 | 13 006 |
| Cached read / write | 0 / 0 | 0 / 0 |
| Input + output / totalTokens | 18 803 | 18 907 |
| Вызовы инструментов | 0 | 0 |

Проверяющие согласны, что все четыре текста поддержаны источниками, уровень — postdoc, срок контракта нужно перенести из `workload` в `appointment_duration`, старое объявление не доказывает текущий набор. Основные расхождения:

| Ось / атомы | Sol | GLM |
|---|---|---|
| Личность / связь объекта, все четыре атома | insufficient: не установлена связь сотрудника CUHK с фиксированным профилем | supported: считает страницу сотрудника и объявление достаточными якорями |
| Профильная личность | insufficient | supported |
| Нынешняя аффилиация | insufficient | conflicting: вуз профиля и CUHK |
| Активность | insufficient, unknown | supported, active; использует недатированную запись, проверенную 09.10 |
| Дата c3/c5/c7 | source_metadata | content; дата у обоих 2023-05 |
| Применимость c5/c7 | historical | expired |
| Вид факта c5/c8 | literal | intake |

Различаются также наборы evidence_refs, объяснения, вопросы и summary; полный покомпонентный diff — `differences.json`. Таблица описывает решения, не выбирает правильное. Sol не эталон; Astra-судейства, человеческой разметки и поиска пропусков нет. Один использованный профиль проверяет работоспособность, не позволяет выбрать лучшую модель или сравнить качество/полноту каталога. Разное input/output и время могут зависеть от клиента, контекста, токенизатора и reasoning; причинное сравнение не проведено. Transport retries Codex не раскрыты; повторных CLI-заданий нет, у Pi обе настройки повторов выключены и наблюдён один model request.

## Сохранённые доказательства и передача

Постоянный отдельный каталог: `/Users/boris/Experiments/search-for-research/enrichment-verifier-pair-20261009` (частные материалы не включены в git).

- `manifest.json`, `instruction.txt`, `schema.json`, `inputs/A5015573260.json`, `prompt.txt`: заморозка задания; material SHA `ef94a4f83f8abab7cb119dd140e3066ee2641e46860882d111470f24deb210f7`.
- `adapter-snapshot/`, `adapter-postflight/`, `adapter-final/`, `diagnostic.py`, `diagnostic-v2.py`, `recovery-version.json`, `failures/sol.json`: версии и первоначальный технический отказ; повторных model attempts нет.
- `runs/A5015573260/native_verifier/`: исходный `raw-result.json`, events, stderr, command, requested config, start/finish/receipt, полные render и `isolation-probe.json`.
- `runs/A5015573260/pi_verifier/`: исходное завершённое assistant-сообщение в `pi/*-session-event.json`, `result.json`, request, stdout/stderr, inventory, stream/runtime settings, HTTP и receipt.
- `results/`, `validation/`, `pair.json`, `differences.json`, `measurements-final.json`: отдельные производные валидации и сравнение. Pair SHA `e582c11f63c02f84d7bd5acd675954fe887abcca8aa02ee68a483802809a6e90`.
- `old-snapshot.json`, `old-preservation.json`: все 51 файла остановленного cache root сохранены, изменений/добавлений/удалений 0, включая STOP. Другие прежние roots не использовались для записи.

Локальные проверки: `make lint`, `make typecheck`, `make test` (180 unittest; 388 pytest, 8 skipped, 5 deselected, coverage 94,06 %), 17 Node-тестов runner и `make docs-check` с `SFR_INDEX_META` из фактического существующего индекса. Strict `make audit AUDIT_ARGS="--no-images --strict"` — FAIL deps-node/fs-trivy, два прежних HIGH sharp/source-map-js, отдельный #189. Зависимости и критерии не меняются. Стандартный history scanner в worktree показал 0 коммитов из-за несмонтированного общего git-dir; отдельный read-only запуск с общим git-dir проверил 446 коммитов, утечек нет. Эти дополнительные доказательства не превращают strict audit в PASS.

Независимое review-iteration, актуальные base/head, CI и readonly `make handoff-check PR=194` фиксируются новыми комментариями [PR #194](https://github.com/borisboriov/search-for-research/pull/194). Наличие пары не снимает #189 и не разрешает merge. #193 остаётся открытой: большой эксперимент не выполнен. Продуктовые документы, паспорт, production, сборщик, остальные 11 профилей не менялись. Паспорт обновлять не требуется; результат только диагностический, не принятый продуктовый факт. Запись прекращается после сохранения проверок и публикации итоговой передачи; новые задания/чаты, мониторинг, merge и deploy не выполняются.
