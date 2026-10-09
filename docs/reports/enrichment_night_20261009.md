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


## Разрешённое продолжение 10.10: literal-format-v5 и пустой gate

[Узкое поручение](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6089090080),
[новый freeze](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6089252765).
Переданный head `bd63a010b668832de86ced57b278b9bd6c92d806`; содержательная версия
`52c3ca25761a13db7bf484b80aa9f388a5ee577e`. Это продолжение той же разрешённой
ночи, без новой итерации. Предыдущие числа/сырые данные/STOP выше сохранены.
Все новые числа сформированы из receipts/results в
[отдельном артефакте](enrichment_night_literal_v5_20261010.metrics.json),
с SHA ссылочных материалов и кодом анализа в private validation.

### Оформление цитат и две повторные проверки

Binder допускает восстановление только при единственном полном соответствии
непрерывному фрагменту одного тела того же reader URL. Нормализация ограничена
NBSP/обычным пробелом, апострофами ‘/’/обычным и структурными bullet/ATX prefixes
Markdown. Пробелы и переносы не схлопываются; semantic/fuzzy matching, перестановки,
склейка blocks и snippets запрещены. При неоднозначности цитата отклоняется.
Выход — исходная точная цитата с Unicode offsets start/end, body/raw SHA и ссылкой
на неизменный reader. Первоначальная кандидатная цитата/причина отказа сохранены
с disposition и provenance восстановления. Прямое буквальное совпадение использует
прежний путь; уникальность требуется именно для восстановления.

| Сохранённый вход | Восстановлено цитат | Возвращено атомов | Supported у Sol и сохранённого Astra¹ | Осталось неизвестным/отклонённым |
|---|---:|---:|---:|---|
| ИТМО / A5011844904 | 2 | 1 | 1 | Склейка JMIR: 1 цитата/5 зависимых атомов; текущие аффилиация ИТМО и активность unknown |
| МГУ / A5061174451 | 1 | 2 | 1 | Город: текст недостаточен; контакт исторический, 2021, актуальность unknown |

¹ Ограничение partly_unblinded этого Astra описано ниже; полная слепая приёмка не выполнена.

Итого3 точные цитаты и3 атома восстановлены до Sol; два контактных атома получили
supported, вывод о городе — insufficient. Имя/аффилиация в CV Иннополиса не
достраивались, смысл graduate/10+ не исправлялся. Полные офлайн восстановления
двух реальных входов и отрицательные ambiguity/glue/other-source fixtures сохранены.
Профили, все прежние атомы/цитаты, полная инструкция и output schema Sol совпали
по SHA/содержимому; вход расширен только описанным восстановлением. Envelope/sample
SHA новые, raw прежний. Collector повторно не запускался; на каждом ID ровно один
новый pipeline verifier, без retry/редактирования модельного результата.

| Вход, отдельный denominator2 | Атомы / исходное положительное покрытие | Identity / current affiliation / activity |
|---|---:|---|
| A5061174451 | 9 / 5 | supported / supported / supported |
| A5011844904 | 1 / 1 | supported / insufficient / insufficient |

Покрытие этих двух входов4→6 атомов относится к новым материалам, не смешивается
с прежним denominator12. Поддержанная агентами идентичность ИТМО не подтверждает
текущую связь с ИТМО. Контакт там без даты; контакт МГУ из2021. Проверка сегодня
не делает их текущими и не доказывает готовность/набор. Это агентские оценки,
не независимый человеческий эталон.

### Пустой gate и свежий контроль

model_not_called/unknown только при items=[] **и** отсутствии всего допустимого
pool/profile_evidence. Каталог не независимое доказательство. Непустое evidence
при items=[] обязательно направляется в полную Sol/high; сохранённый МИСиС с
identity evidence не попадает в gate. Новый учёт допускает verifier_receipt=null
только для доказанного пустого случая, без выдуманного receipt/модельной оценки.

Обычным кодом прочитаны12 сохранённых входов и фактический usage прежних receipts.
Gate-only на прежних пакетах: 5 случаев, 85 141 ранее израсходованных input+output токенов.
Gate совместно с разрешённым восстановлением двух входов: 4 случаев, 68 143 ранее израсходованных input+output токенов.
Это counterfactual estimate; старые доказанные расходы не меняются. Восстановленный
ИТМО больше не пустой, поэтому экономия совместного метода меньше gate-only.

Три разных вуза заранее закреплены seed19319420261016; исключены все136 прежде
выбранных ID, включая failed/not-started. Сначала1, затем2 по одному после штатных
исходов и свежих официальных quota snapshots. Pi CLI GLM/high:4search/8resources
incl robots/6requests/600s/concurrency1; лимиты не увеличивались.

| Свежий ID / вуз | Collector requests | Поиски / reader / host robots | Секунды collector | Допустимые атомы/evidence | Sol |
|---|---:|---|---:|---|---|
| A5080057408 / Иннополис | 5 | 3 / 0 / 1 | 79.42 | 0 / 0 | model_not_called |
| A5101711419 / ВШЭ | 5 | 4 / 1 / 1 | 121.57 | 0 / 0 | model_not_called |
| A5111695924 / МАИ | 5 | 3 / 0 / 0 | 76.46 | 0 / 0 | model_not_called |

Все3 штатно завершены, фактов0, все три профильные оси insufficient. Это unknown
при ограниченных источниках, не отрицание сведений/набора. Пустота присутствовала
уже в raw collector; binder не потерял здесь цитаты. Реально пропущено
3 Sol jobs; input/output расход на них0, native directories/receipts отсутствуют.
Сколько токенов понадобилось бы незапущенным моделям, неизвестно; число старого
counterfactual не выдается за фактическую экономию свежих3.

Живой путь **после** исправления host deadline теперь пройден3 раза. Зафиксированные
финалы раньше600с, partial/timeouts0. Это малый контроль штатного пути; зависшие
DNS/robots/игнорирование SIGTERM проверены фикстурами, не искусственным живым
обходом ограничений. Полезное покрытие свежих3 не подтверждено, расширение поиска
в этом scope не выполнялось.

### Ограничение слепого пакета и фактические расходы продолжения

Один Astra/xhigh job:2 восстановленных+первый свежий. Независимый финальный
ревьюер обнаружил нарушение слепоты: четыре строки summary ответаA свежего
A5080057408 содержали «Sol не вызывался». Этот пакет действительно включён в
native prompt судьи. Поэтому запуск имеет статус **partly_unblinded**;
полная слепая приёмка этим запуском не выполнена. Provenance/ожидаемые вердикты
не передавались, добавочного поиска не было, но название модели в естественном
тексте было раскрыто. Повторный Astra не запускался: разрешённый лимит использован.

SHA/seals/schema и соответствие всем атомам/осям проверены. Сохранённый судья
отметил correct для10/10 классификаций атомов (включая корректные insufficient)
и9/9 профильных оценок; high/critical0. Эти числа сохранены без изменений и
относятся к малому, частично раскрытому агентскому аудиту. Они не доказывают
слепую приёмку,100% точность поиска, полноту или human truth. Human_reviewed=0.

Измеренные packet/prompt/raw/receipts/results и private metrics-final.json
не перезаписывались. Отдельный immutable validation/blinding-qualification.json
фиксирует affected ID/поле, причину и SHA; публичный числовой документ дополнен
этим ограничением, прежняя числовая часть совпадает с private metrics.
13 исходников/правил измеренной версии52c3ca2 сохранены с manifest SHA в
validation/source-at-52c3ca2. Будущий host gate исправлен: его summary/explanation
содержат только неизвестность и отсутствие доказательств; model_not_called
остаётся в техническом provenance. Исправленная формулировка не выдаётся за
измеренный запуск, старые roots получают отказ locked() при изменённых правилах.

| Стадия новых физических jobs | Jobs | Input+output | Cached input (часть input) | Сумма секунд | Физические requests |
|---|---:|---:|---:|---:|---|
| GLM collector | 3 | 88 307 | 28 928 | 277.46 | 15 |
| Sol verifier | 2 | 39 717 | 0 | 158.10 | unknown |
| Astra judge | 1 | 25 335 | 0 | 103.99 | unknown |

Новых содержательных jobs6/12 разрешённых; итог ночи
40/100, свежих людей15/30, Astra3/4 (один остаётся в резерве).
Повторов model jobs0, провайдерных transport retries native unknown.
Коллекторы в replay profile_metrics — переиспользованные исторические receipts;
их токены/время **не** входят в новую таблицу физических jobs. Числа трат,
backend и ёмкость подписок не выводятся из конфигурации/API-прайса.

Перед content calls Codexremaining33%; после партии32%, account-wide. Передача
была34%; дельта не отделена от других чатов. GPT stop≤15% не достигнут;
reset-credit/покупки/API оплаты не использованы. GLM actual quota/tier/debit остаются
unknown; изменение условий масштабирования не исследовалось заново.

Разработка/ревью отдельно — cumulative token_count по двум собственным акторским
журналам на явном cutoff, snapshots не суммируются. Cached/reasoning — уже части
input/output, время включает ожидания. Последующий финальный recheck/публикация
после cutoff сюда не входят; raw журналы/рассуждения не экспортированы.

| Актор | Cutoff UTC | Input | Cached input | Output | Reasoning в output |
|---|---|---:|---:|---:|---:|
| independent_code_review | 2026-10-09T21:03:43.872Z | 1 793 415 | 1 635 584 | 8 741 | 2 455 |
| technical_session_orchestration | 2026-10-09T21:17:45.264Z | 9 564 878 | 9 355 520 | 52 594 | 19 748 |

### Проверки, сохранность и передача

На содержательной версии52c3ca2 `make lint/typecheck/test` PASS:216 unittest,
388 pytest,8 skipped/5 deselected, coverage94,06%; Node21 PASS; docs-check с
действующим index meta PASS. Strict audit снова FAIL только deps-node/fs-trivy
по двум прежним HIGH sharp/source-map-js (#189); критерии/зависимости не менялись.
Stock history scanner в linked worktree видит0commits; дополнительный локальный
запиненный gitleaks с двумя readonly mount/без сети проверил462commits/10,94MB,
no leaks. CI кода52c3ca2: [web PASS, checks FAIL до тестов](https://github.com/borisboriov/search-for-research/actions/runs/37991253471)
из-за unauthenticated Docker Hub pull limit postgres17.11;
[audit FAIL #189](https://github.com/borisboriov/search-for-research/actions/runs/37991253303).
Никакого обхода квот/изменений CI нет. Финальное подтверждение ревью/актуальный
CI и readonly handoff публикуются в PR после коммита этого раздела.

Предзапусковой reviewer нашёл Medium freeze_saved на policy source_finished без
raw_file; исправлено4fc39d0 и проверено fixture с настоящими Batch. Recheck2717198
PASS, включая совпадение CLI_METHOD/METHOD. Реальный offline preflight обнаружил
allowlist mismatch до inference; отказ/STOP сохранён, исправленный freeze отдельно.
Оба исправленных preflight прошли с0inference. Финальный recheck учитывает также
нулевой gate в метриках и результаты; авторская проверка не подменяет его.
Финальный recheck74e9584 выявил описанное раскрытие модели в судейском пакете.
Уточнение отчёта и будущей формулировки передано на повторное независимое ревью;
методологическое ограничение фактического запуска остаётся видимым.
После исправления формулировки повторно прошли lint/typecheck/test
(216 unittest,388 pytest, coverage94,06%), Node21 и docs-check. Strict audit
снова завершился только deps-node/fs-trivy FAIL по тем же двум HIGH из #189.
На74e9584 web PASS, checks FAIL из-за Docker Hub authentication timeout
до checkout/tests, audit FAIL #189. Статус последней версии после уточнения
публикуется отдельным подтверждением ревью и handoff в PR.

Private roots: `/Users/boris/Experiments/search-for-research/` плюс
`enrichment-night-literal-format-v5-replay-20261010` (подготовка/отказ/counterfactual),
`enrichment-night-literal-format-v5-replay-fixed-20261010` (два Sol/судья/metrics/validation),
`enrichment-night-literal-format-v5-fresh-20261010` (3 collector/gates).
Карточки `cards-replay.html` и `cards-fresh.html`; html static export, визуальное
браузерное подтверждение не заявляется. Полные источники/контакты внеgit.

Старые9roots не записывались,124917 ранее проверенных файлов повторно не копировались
и не перечитывались целиком. Для использованных12 input/result SHA проверены;
для восстановленных reader точные spans/body/raw SHA совпали. Все прежние
подтверждённые метрики/STOP/raw сохранены. Новые finished/receipts/raw/seals и
числовые исходы неизменяемы, собственные content процессы закончены; новые roots
получилиSTOP. Ветка/worktree сохраняются для завершения раунда после решения Бориса.

Итог узкого этапа: три цитаты перестали теряться, три Sol вызова реально исключены,
3/3 свежих штатно закончены. Нового покрытия свежих профилей нет; устойчивость
массового конвейера, текущие контакты/набор, human accuracy и подписочная ёмкость
не установлены. PR остаётся blocked по#189, готовность CI/handoff не заявляется.
#193/#47/#103 не закрываются. Нет merge/main push/deploy/production/product docs/
паспорта. Раннее завершение этой сессии не отменяет разрешённую Борисом ночь до
05:00МСК; дальнейший scope в её пределах определяет продуктовый координатор.


## Последний этап 10.10: early-read-v6, парные последние попытки

[Постановка до calls](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6090040750),
[передача продуктового потока](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6089940389).
Измеренный head `4de4a8f1ddf895a861fd956d01f86c460cf6b7ce` после b06;
[правила](../experiments/enrichment_cli_early_read_v6.md),
[новый числовой артефакт](enrichment_night_early_read_v6_20261010.metrics.json).
Это **парное сравнение маршрутов тех же3**, вторая и последняя collector попытка
каждого ID. Новый контроль не запускался. Итоги v5/compact/старого судьи неизменны.

### Что зафиксировано до измерения

Изменён существующий collector/CLI extension: первый exact basic query — имя
и ORCID либо индексированная публикация. URLs прежних поисков передаются как
discovered, без статуса evidence; прежние неудачные URLs не повторяются. Reader
допускает только exact найденный link. При request≥3 без тела и с доступным URL
новый поиск отклоняется; request4 оставлен для альтернативного чтения после
отказа/оболочки. Каталог не подтверждает нынешний вуз. Вымышленная кафедра/URL
не допускается. Все4search/8resources includingrobots/6requests/600s/concurrency1,
source cutoff before5, retries0, full Sol/high, literal binder и empty gate сохранены.

Заранее выбран технический минимум тела:200UTF16 code units (native JS string
length) и30Unicode letter/number words в decoded reader content. Snippet/metadata
не входят. **Это прокси непустого текста, не полезная страница о человеке и не
подтверждение личности.** Цель первого содержательного целевого чтения — не позже
request3. Отдельно измеряются profile evidence/identity и допустимые факты.
Порог условного нового профиля:≥2/3с телом по замороженному минимуму и≥1с supported
identity либо supported фактом по полной проверке. Порог не менялся после исходов.
Measurement-plan и код анализа с SHA сохранены доcalls; source snapshot11 файлов
из manifest соответствует4de4a8f. Offline fixture foundURL→earlyread и
refusal/shell→другая найденная ссылка прошёл; третий collector запрещён при freeze
и перед запуском. Предварительный независимый reviewer:pass для кода до inference.

### Результат: больше чтений, полезное покрытие не улучшилось

| Парный ID | Физические search / reader / host robots | Model requests | Секунды | Тела по техническому минимуму | Atoms / evidence / supported identity |
|---|---:|---:|---:|---:|---:|
| A5080057408 | 1 / 0 / 1 | 5 | 63.27 | 0 | 0 / 0 / 0 |
| A5101711419 | 2 / 2 / 2 | 5 | 288.01 | 0 | 0 / 0 / 0 |
| A5111695924 | 2 / 1 / 1 | 4 | 237.78 | 1 | 0 / 0 / 0 |

Все3 завершились штатно, partial/timeouts0. **Допустимые нормализованные**
пакеты пусты у всех3:0atoms,0pool,0profile refs. Первые два уже пусты вraw.
Raw МАИ содержит5тематических атомов и1цитату общей страницы программы;
1цитата отклонена как quote_not_literal_or_unread, её5зависимых атомов —
no_valid_literal_evidence. Все6отклонений/кандидаты сохранены. Это не потеря
доказанных сведений о человеке: ни identity refs, ни подтверждённого личного факта
нет; темы учреждения не переносятся на исследователя. Таблица/числовой JSON
показывают допустимые atoms/evidence после binder, raw denominator отмечен отдельно.
Три host gate дают insufficient/unknown по всем осям. Sol не вызван3 раза,
расход0; avoided tokensunknown. Это отсутствие доказательств в ограниченном
маршруте, не отрицание фактов/набора у людей.

Иннополис: первая строка модели сократила ORCID URL из frozen basic query до ID
и была отклонена exact first-query guard. Реальный поиск произошёл наrequest2;
следующий поиск наrequest3 отклонил route guard. Единственное reader намерение
наrequest4 выбрало другую языковую ссылку Scholar, host robots запретил доступ.
Физического reader0, цель раннего полезного чтения не достигнута. Обхода robots
не было; повторной попытки этого ID не будет.

ВШЭ: reader наrequest3 и альтернативный наrequest4 вернули212UTF16/26words и
193UTF16/39words. Оба ниже заранее установленного совместного минимума;
не добавлены допустимые anchors/факты. После ORCID модель вновь использовала
неподтверждённый вуз в поиске. Запросы/цитаты не исправлялись после получения.

МАИ: наrequest3 прочитано2050UTF16/214words общей страницы федеральной программы
`fcpir.fcntp.ru`. Текст проходит длиновой минимум, но в нём нет Nenarokomov/
Ненарокомов или выбранного названия публикации. Это **1техническое тело**, а не
полезная страница исследователя. Предметная идентичность/факты0. Вымышленный
`101.mai.ru` не повторялся, источник текущей кафедры не додумывался.

По тем же3 v5→v6: реальные reader1→3, тела по минимуму0→1, полезные факты/
supported identity0→0. Целевое полезное чтение доrequest3 не подтверждено ни у
одного. Инструкции/guard улучшили число чтений, но не обеспечили выбор предметных
страниц в малом бюджете. **Полезность метода не подтверждена**; успешные fixture
и completed не выданы за улучшение доказанного покрытия.

### Условные вызовы и расходы

Контрольный A5014957454/МГТУ заранее заморожен отдельно из другого вуза, отсутствует
в139 исключённых ID. Порог не выполнен (1/3технических тел,0полезных результатов):
его collector/verifier не запускались. Last Astra также не запускался — полезного
нового результата нет; резерв1сохранён. Новый single-response export/selection
план сохранён, но фактического нового packet/prompt/audit нет. Прежний
partly_unblinded v5 остаётся ограниченным; full blind acceptance не заявляется.
Human_reviewed0; контакты не равны готовности, история не равна нынешнему набору.

Новых содержательных jobs3/10: только GLM collector; модельных retries0.
Глобальный итог ночи43/100jobs,15/30новых людей,3/4Astra. Один выбранный условный
ID не выдаётся за реально проверенного свежего человека.14client model requests
подтверждены14HTTP200 chat/completions записями; фактический backend не раскрыт.
Source calls по successful reservations:search10→5,reader1→3,hostrobots2→4;
MCP protocol discovery/202/405 не считаются содержательными запросами источников.

| Парная стадия GLM, отдельно3+3 jobs | Input+output | Сумма секунд |
|---|---:|---:|
| v5 | 88 307 | 277.46 |
| v6 | 113 156 | 589.06 |

Итого v6:input88 886 (cached25 536 уже внутри input),output24 270 (reasoning22 084
уже внутри output),total113 156. Токены выросли на28.14%,
collector time на112.31% при нулевом приросте полезного покрытия.
Денежный debit/GLM quota unknown; API-прайс не подставлялся вместо подписки.
Официальные snapshots доcalls/следующей партии/после:Codexremaining30%,account-wide;
до разработки31%. GPT stop≤15% не достигнут, reset/purchase/APIоплаты нет.

Разработка/ревью отдельно — cumulative snapshots собственных акторов на cutoff,
включая прежнюю работу этого чата. Их не суммировать с таблицей v5 или content jobs.
Cached/reasoning — части input/output; raw logs не экспортированы, actual backend
unknown. Последующее финальное review/публикация после этих cutoff исключены.

| Актор | Cutoff UTC | Input | Cached input | Output | Reasoning в output |
|---|---|---:|---:|---:|---:|
| independent_code_review | 2026-10-09T22:09:36.893Z | 6 052 464 | 5 727 616 | 28 803 | 7 491 |
| technical_session_orchestration | 2026-10-09T22:28:32.772Z | 20 343 067 | 19 946 496 | 144 810 | 69 664 |

### Проверки и сохранность

Lint/typecheck/test PASS217unittest/388pytest,coverage94,06%; Node22/docs-check
actual index meta PASS. Strict audit FAIL только прежние deps-node/fs-trivy HIGH
sharp/source-map-js #189; зависимости/критерии не менялись. CI4de:
[checks/web SUCCESS](https://github.com/borisboriov/search-for-research/actions/runs/37997447269),
[audit FAIL #189](https://github.com/borisboriov/search-for-research/actions/runs/37997447291).
Актуальное финальное review/CI/readonlyhandoff публикуется в PR после коммита
раздела. Зелёная готовность или продуктовая приёмка не заявляется.

Private roots в `/Users/boris/Experiments/search-for-research/`:
`enrichment-night-early-read-v6-paired-20261010` (manifest/source snapshots,
measurement-plan/version,3raw/receipts/gates/results,cards.html,metrics-final,
conditional-decisions,quota/actor cutoff и validation),
`enrichment-night-early-read-v6-control-20261010` (один sample/manifest,не запускался).
Числовой public JSON совпадает с private metrics-final byte-for-byte; полные
source bodies не вgit. Исходник анализа с исходным SHA доступен в private
validation/sfr-v6-measure.py, временный creation path вmeasurement-plan — provenance.
Все25 ссылок на старые парные данные совпали; старые9roots/124917файлов целиком
не перечитывались и не записывались. Собственные content processes закончены,
оба новых roots STOP. Ветка/worktree сохраняются; после окончательной передачи
запись исполнителя прекращается, дальнейший этап определяет продуктовый поток.
