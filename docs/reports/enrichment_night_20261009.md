# Ограниченный конвейер и экономия GPT, ночь 09–10.10.2026

PR [#194](https://github.com/borisboriov/search-for-research/pull/194), issue #193.
[Поручение Бориса](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6086727260).
Переданная ветка `codex/enrichment100-20261008`, исходный чистый head
`a4c7d93545f2abaa311df6fe39c8689e60d1346a`.

Завершены 12/12 основных профилей. Конвейер сохраняет публичные
источники, дословные доказательства, независимый Sol/high и читаемые карточки.
Результат технического эксперимента остаётся в ветке; продуктовой приёмки,
merge и выкладки нет. Human_reviewed=0 на всех стадиях.

Числа ниже автоматически сформированы из сохранённых receipts/results в
[числовом артефакте](enrichment_night_20261009.metrics.json); SHA исходных
измерений включены в него. Деньги, фактический backend и неизвестные значения
не подставлены из конфигурации или API-прайсов.

## Метод и сохранность

Сборщик использует документированный native Pi CLI, `zai/glm-5.3-flash/high`,
session-local MCP extension и host budget: 4 search, 8 resources **включая
host-only robots**, максимум 6 model requests, concurrency1, 600с на job.
V4 прекращает источники перед пятым запросом/через360с/при исчерпании бюджета;
последнее user сообщение требует законченный JSON. Retry0, compaction/warming off.
См. [bounded-v4](../experiments/enrichment_cli_bounded_v4.md).

Sol6.1/high выполняется штатным Codex CLI в отдельном пустом workspace без
tools/MCP/browser. Запрошенные model/effort фиксируются; actual backend/model
metadata и число физических provider requests native Codex не раскрыты/null.
Receipt, raw, events и prompt сверяются по SHA; схема проверяется до нормализации
служебного provenance. Цитаты связываются с буквальными reader фрагментами.
Групповой набор не переносится на человека, email не считается готовностью.
Content date и checked_at разделены; отсутствие сведений остаётся unknown.
Обязательные домашние сообщения native Codex — ограничение клиента; домашние
файлы намеренно не включались в задания, профильные материалы не сокращались.

Fixed sample закреплена до calls: 12 вузов, прежние выбранные ID исключены,
включая неуспешные/не запущенные. Первые три результата восстановлены/переиспользованы
из предыдущего раунда, остальные девять выполнены v4. Это смешанный ряд v2/v4,
а не двенадцать независимых прогонов одной версии.

Сохранены все неуспехи: v1 первый collector потерял IPC stdout (39,996с,
1 request, known3440tokens, no sources); второй collector v2 был штатным,
но host dictionary checker упал до Sol; v3 восстановил его raw офлайн без
третьего GLM. На четвёртом профиле первый collector завершил6requests
обещанием JSON без JSON (180,603с,52670tokens); v4 выполнил только вторую
исправленную попытку. Подробности: [v2](../experiments/enrichment_cli_bounded_v2.md),
[recovery](../experiments/enrichment_cli_recovery_v1.md). Автоматических повторов нет.
Пустые v3 и первый compact root остановлены до inference, сохранены со STOP.

Заключительная SHA/size/file-list сверка **True**:
9 roots,
124,917 файлов,
добавлений/удалений/изменений0. Старые метрики/разметка/STOP/raw не переписаны.
Ранний checkpoint03 ошибочно предполагал native requests=1/job;
он сохранён как история, текущий агрегат использует null.

## Покрытие двенадцати профилей

| Вуз / OpenAlex ID | Кандидаты | Положительное покрытие исходных полей, атомы | Поля | Identity / current affiliation / activity |
|---|---:|---:|---|---|
| Иннополис / A5079662185 | 7 | 0 | unknown | supported / insufficient / supported |
| ВШЭ / A5047730452 | 4 | 1 | topic | supported / supported / supported |
| МАИ / A5041484793 | 0 | 0 | unknown | insufficient / insufficient / insufficient |
| МГТУ / A5068285041 | 0 | 0 | unknown | insufficient / insufficient / insufficient |
| МГУ / A5061174451 | 7 | 4 | personal_contact, supervision_history, supervisor_role | supported / supported / supported |
| МФТИ / A5040643973 | 2 | 1 | topic | supported / insufficient / insufficient |
| МИСиС / A5039855737 | 0 | 0 | unknown | insufficient / insufficient / insufficient |
| МИФИ / A5053581596 | 0 | 0 | unknown | insufficient / insufficient / insufficient |
| НГУ / A5026442137 | 5 | 2 | personal_contact | supported / supported / supported |
| СПбГУ / A5039216145 | 0 | 0 | unknown | insufficient / insufficient / insufficient |
| ИТМО / A5011844904 | 0 | 0 | unknown | insufficient / insufficient / insufficient |
| УрФУ / A5008895365 | 2 | 1 | topic | supported / supported / insufficient |

Итого кандидатных атомов 27,
дословных цитат 30,
отклонённых кандидатов 39,
положительное исходное покрытие 9.
Профессиональные контакты/история руководства найдены у
2 профилей.
Подтверждённого published_recruitment/direct_willingness/coordinator_contact нет.
У 6 профилей нет пригодных атомов.
Дополнительные/исторические поддержанные факты перечислены отдельно в JSON
и карточках; они не увеличивают исходное покрытие18полей.
Существующие темы/публикации взяты из каталога, не собирались заново.
Идентификационная оценка Sol не является измеренной человеческой точностью;
для этих12 нельзя заявлять долю ложной идентификации/набора по независимому эталону.

Локальные карточки:
`/Users/boris/Experiments/search-for-research/enrichment-night-cli-v4-20261009/cards-final-12.html`.
Открытие в native Codex file panel queued для скрытого технического чата.
HTML/экранирование/ссылки проверены статически; визуальная браузерная проверка
не выполнена из-за ограничения file URL, обхода не было.

## Сравнение GPT

[Пререгистрация](../experiments/enrichment_gpt_compact_v1.md): три старых сложных
входа, шесть новых Sol/high jobs, одна и та же полная source JSON и все identity
anchors/цитаты. Baseline — полная инструкция со schema в prompt+output-schema;
compact — [краткая инструкция](../experiments/enrichment_verifier_compact_v1.md)
и schema только в output-schema. Два слепых Astra/xhigh judges, случайные A/B,
без названия варианта, model/usage/provenance; packet/mapping/seals связаны с raw.
Порог input≥15%, input+output≥10%, correct atoms/axes не ниже baseline,
нет новых/усиленных конкретных high/critical. Время/кэш зависят от порядка,
это не причинная оценка ускорения и не универсальная оценка экономии.

| Вариант, 3 jobs | Input | Output | Cached input | Reasoning в output | Input+output | Сумма секунд |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 50 053 | 8 446 | 0 | 3 168 | 58 499 | 204.10 |
| compact | 45 181 | 7 101 | 8 320 | 2 213 | 52 282 | 166.73 |

Снижение input: 9.7%; input+output: 10.6%. Допуск свежего контроля: **False**.

| Вариант | Correct atoms | Correct axes | High/critical |
|---|---:|---:|---:|
| baseline | 10 | 8 | 2 |
| compact | 6 | 8 | 0 |

Новые/усиленные high/critical: `[]`. Это агентская слепая проверка, не human ground truth.

| Вариант | Оценка | Severity | Тип ошибки | Количество |
|---|---|---|---|---:|
| baseline | atom_evaluations | high | identity | 2 |
| baseline | atom_evaluations | high | object_relation | 2 |
| baseline | profile_evaluations | medium | text | 1 |
| compact | atom_evaluations | medium | object_relation | 6 |
| compact | profile_evaluations | medium | text | 1 |

Одна оценка может иметь несколько типов ошибки, строки не суммируются в число неверных атомов. Конкретные оценки без source/contact текста сохранены в JSON. Полная инструкция тоже не даёт эталона и требует отдельной фактологической приёмки.

Свежий контроль не запускался: условие допуска сравнительного этапа не выполнено.
Метод дополнительного этапа: [fresh compact control](../experiments/enrichment_fresh_compact_control_v1.md).

## Физическая работа и расходы

Общий учёт включает неуспехи и дедуплицирует копии одного receipt/agent_id;
started без receipt учитывается как partial. Reasoning входит в output,
cached input — часть input. Pi cached read прибавляется к uncached input
один раз; native Codex input уже включает cache. Ниже full total unknown
при неполном usage, известный subtotal сохранён отдельно.

| Стадия | CLI jobs | Сумма секунд | Полный input+output | Known subtotal | Физические model requests |
|---|---:|---:|---:|---:|---:|
| collector | 14 | 3022.57 | unknown | 631 936 | 69 |
| comparison_verifier | 6 | 370.82 | 110 781 | 110 781 | unknown |
| judge | 2 | 260.87 | 51 286 | 51 286 | unknown |
| native_verifier | 12 | 622.24 | 224 456 | 224 456 | unknown |

Физические source operations за всю ночь (включая неуспехи):
search 41,
reader 33,
host robots 30.
Budgets без receipt: 0.

Работа основного разработчика и независимого ревьюера отдельно, cumulative
numeric token_count на указанный cutoff; повторные snapshots не суммируются.
Большая часть input — cached, время включает ожидания/перекрывающиеся jobs и
не является чистым временем разработки. Последующие публикации/финальное ревью
после cutoff не входят; raw журналы/домашние сообщения не экспортировались.

| Актор | Cutoff UTC | Input | Cached input | Output | Reasoning в output | Интервал секунд |
|---|---|---:|---:|---:|---:|---:|
| independent_code_review | 2026-10-09T20:25:50.983Z | 15 001 937 | 14 268 544 | 68 729 | 26 609 | 6884.75 |
| technical_session_orchestration | 2026-10-09T20:33:14.888Z | 35 358 874 | 34 515 968 | 247 182 | 115 363 | 8297.93 |

Официальные account-wide quota snapshots находятся в JSON. На старте
Codex used58%/remaining42%; дельта этой сессии не отделена от других чатов.
При remaining≤15% новые GPT jobs запрещены, reset-credit/покупки не использовались.
GLM actual tier/quota/debit/payment unknown: официальная quota page требовала login.
API-цены не используются для пересчёта подписки. Цель $100–200/месяц на
GPT/Codex плюс GLM пока не подтверждена измеренным платежом/лимитом.

## Условные сценарии 60 дней

Линейная экстраполяция только 12 completed profiles
с mixed-method baseline verifier; исключает ошибки, разработку, ревью,
очереди и человеческую работу. Если свежий compact control выполнен, его
отдельный denominator2 приведён в JSON, с основным рядом не смешан.

| Цель | Профилей/день | Последовательные model часы/день | GPT tokens/день | Документарные GLM credits/день |
|---|---:|---:|---:|---:|
| 1000 | 17 | 1.35 | 317 979 | 237.31–359.02 |
| 10000 | 167 | 13.24 | 3 123 679 | 2331.24–3526.88 |

Это нагрузка при линейном сценарии, не обещание пропускной способности.
Human hours, реальная quota capacity, subscription money и commercial scale
permission неизвестны. Каталог содержит9002людей, поэтому10000различных
профилей не покрывает даже исходная база. Ограниченное покрытие контактов
и отсутствие доказанного набора дополнительно ограничивают продуктовую ценность.

[Официальный Pi](https://docs.z.ai/devpack/tool/pi) поддерживает штатный клиент.
[Overview](https://docs.z.ai/devpack/overview) описывает research/office и
автоматизацию в поддерживаемых инструментах, квоты Lite/Pro/Max
2000/12000/28000 за5ч и10000/60000/140000 за неделю. Документарная формула
Flash credits: `(uncached_input×2.3+cached_input×0.56+output×8)/10000`;
model off-peak0.5x, search/reader1.2credit; host robots не MCP credit.
Это не проверенный tier/debit аккаунта. [Subscription terms §4](https://docs.z.ai/legal-agreement/subscription-terms)
ограничивает SDK/general-purpose API и предоставление модели третьим лицам.
Личный native CLI pilot не доказывает допустимость массового продукта;
условия масштабирования остаются отдельным блокером без обхода.

## Проверки, ревью и передача

`make lint/typecheck/test` PASS:206unittest,388pytest,8skipped/5deselected,
coverage94,06%; Node21 и docs-check с действующим index meta PASS.
Реальный native CLI preflight —0 inference, local IPC fixture прошёл.
Offline integrity/schema/mapping/partial-accounting/control/host deadline tests входят в206.
CI измеренной версии `a59169ea45b42d11daeebcedad9170d242ba1582`:
[checks и web PASS](https://github.com/borisboriov/search-for-research/actions/runs/37982634995),
[audit FAIL](https://github.com/borisboriov/search-for-research/actions/runs/37982635088).

Strict audit `--no-images --strict` FAIL deps-node/fs-trivy: HIGH sharp0.35.4
(GHSA-wq5f-xc86-pv6w) и source-map-js1.2.1 (CVE-2026-93749), известный#189.
Зависимости/критерии не менялись. Stock Docker history scanner в linked worktree
проверил0commits из-за внешнего commonGit; это ограничение явно сохранено.
Дополнительная проверка с двумя read-only mount реальных путей проверила
456commits/10.84MB, no leaks. Остальные code/Python/container audit stages PASS.

Независимый sfr-reviewer закрыл находки IPC/quota/deadline, dictionary/schema,
raw integrity/provenance order, partial jobs/provider request accounting.
[Предзапусковой pass на a59169e](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6088210012)
относится к коду, не к последующим outcomes. [Полный проход21файла на a59169e](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6088682667)
отменил его: один Medium блокер синхронного host policy, который мог нарушить
600с/HARD_STOP при медленном DNS/robots/body/crawl-delay.

После завершения всех измерений исправлен [host deadline](../experiments/enrichment_cli_host_deadline_v1.md):
policy изолирована в child process, parent ждёт до min25с/source360с/HARD_STOP−5с,
terminate/kill имеют bounded joins. Timeout останавливает CLI, сохраняет
partial/unknown и блокирует dependent Sol; поздние reserve не запускают policy.
Реальные hung-worker/ignored-SIGTERM/local-CLI фикстуры проходят.
**Новых collector/verifier/judge jobs этого исправленного кода нет**: результаты12 и
сравнение относятся к прежним frozen core hashes, копии21исходника на a591
сохранены в private validation/source-at-a591/source-index.json. Старый root
не возобновляется после изменения core; будущий запуск требует нового freeze.

Итоговый exact-head review и
CI/handoff публикуются в PR после коммита этого отчёта; старый legacy диапазон
PR до a4c7d93 не выдаётся за полностью прочитанный в ночном scope.

DoD:12completed/card export, immutable receipts/failed rounds,
matched comparison и проверка условия свежего контроля, числовой учёт/сценарии,
independent review выполняются в пределах этой ночи. Фактический исход
условного контроля указан выше, отрицательный допуск не разрешает его запуск.
Audit/green handoff не
выполнен из-за#189; human quality/payment/scale terms не установлены.
#193/#47/#103 остаются открыты. Нет merge/deploy/main push, product docs,
паспорт/CustDev не менялись; предложений ячеек паспорта нет.
Работа останавливается по завершении раньше05:00МСК, новые inference партии
после04:30 запрещены. Неуспехи не повторяются автоматически; дальнейшая
работа после ночной остановки требует нового поручения Бориса.
