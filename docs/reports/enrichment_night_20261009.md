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
Raw МАИ повторяет5тем frozen каталога и содержит1цитату общей страницы программы.
Цитата переведена моделью на английский, тогда как reader body русский;
1 цитата отклонена как quote_not_literal_or_unread. Пять topic-атомов уже
в raw имеют evidence_refs=[] и независимо отклонены как no_valid_literal_evidence. Все6отклонений/кандидаты сохранены. Это не потеря
доказанных сведений о человеке: ни identity refs, ни подтверждённого личного факта
нет; темы каталога не получают независимого подтверждения от общего текста программы.
Таблица/числовой JSON
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


## URL-контроль 10.10: native MCP, положительная сохранённая страница

По [узкому поручению](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6090688893)
выполнен один контроль без модельного планирования; [постановка до вызовов](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6090765165).
Заведомо положительный старый reader — Charline Grossard, ISIR,
`https://www.isir.upmc.fr/personnel/grossard` (v4/A5011844904/000063).
До calls закреплены title, anchors Charline Grossard/ISIR и прямой буквальный факт
«Ingénieure de recherche». Поисковая строка:
`"Charline Grossard" "ISIR" "Institut des Systèmes Intelligents et de Robotique"`.
Последние три ID исключены. Это не свежий случай и не добавление к prevalence/mixed12.
Лимиты: 1 search / 2 reader / 4 resources включая robots / 600 секунд,
concurrency1, retries0. Условие GLM/Sol: поиск возвращает точный адрес целевой
страницы, а reader — тело с обоими anchors и буквальным прямым фактом.

Поиск вернул девять результатов. Точные `link` из native raw:

| Заголовок | Возвращённый link |
|---|---|
| ICT and autism care | https://hal.sorbonne-universite.fr |
| Mohamed Chetouani | https://www.isir.upmc.fr/personnel/chetouani/feed |
| Mohamed Chetouani | https://cv.hal.science/mohamed-chetouani |
| Charline GROSSARD — Speech therapist | https://www.researchgate.net/profile |
| Multimodal Personalization of Multi-User Human-Robot | https://dl.acm.org/doi |
| Investigating the Feasibility of a Wizard-of-Oz Robotic | https://nbn-resolving.org |
| Robotique : quel intérêt dans l’autisme ? | https://www.larevuedupraticien.fr/pdf |
| Sofiane Boucenna | https://loop.frontiersin.org/people/overview |
| Investigating the Feasibility of a Wizard-of-Oz Robotic | https://link.springer.com/content/pdf |

**Целевая профессиональная страница ISIR не получена.** Предварительный широкий
критерий «первый результат с именем и институтом в title/snippet» выбрал связанную
статью ICT and autism care, а не ту же профессиональную страницу. Это ограничение
контроля: `selection.json.target_not_retrieved=false` означает только совпадение
с широким критерием; не означает получение целевой страницы. Новых запросов или
исправляющего live-чтения не было. Возвращённый корень HAL передан reader точно:
robots302 отклонён существующей политикой, физический reader этой ссылки не вызван.
Нельзя переносить утверждение «все links — корни» на этот контроль: некоторые links
имеют пути; среди них есть профили другого человека и общие пути без ID документа.

Отдельный прямой контроль передал **известный точный URL** ISIR. Robots200 разрешил
путь, native reader вернул isError, MCP error500/code1234 Network error. Тело,
цитаты и прямой факт текущим вызовом не получены; прежний успешный reader сохранён
раздельно и не выдан за новый результат. Никаких retries/обходов или новых livecalls.

Подтверждённая граница: выбранный search link уже был корнем HAL в durable native
response до нашего readerView; native raw rows и результат MCP client совпали.
Offline сверка существующего readerView сохраняет search values; локальный адаптер
не исправлялся. Использованы штатные Pi1.1.0 McpServerConnection/createDefaultTransport
и существующий serialized capture wrapper, без нового универсального runner или
транспорта. Одноразовая оркестрация фиксированного случая сохранена только private.
Точное различение provider/backend и native Pi parser не сделано: raw HTTP search
payload не сохранён. **Контроль не подтвердил, что потеря адреса — единственная
причина отсутствия тела**: прямой exact URL тоже завершился ошибкой чтения.
Extractor не проверялся, отсутствие фактов у человека не выводится.

Фактически: 1 search RPC, 1 reader RPC, 2 host robots = 3 resources включая robots;
reader attempts2, из них1 host-denied до физического вызова; 10,863 секунды.
Protocol discovery не content calls. Model planning/GLM extractor/Sol/Astra0;
условие извлечения не выполнено. Новых profile content jobs0: прежние43 неизменны;
с отдельно указанной архитектурной консультацией —44 зачтённых задания,
15 новых людей, Astra4/4. Консультация requestedAstra/xhigh, backend/token usage
unknown, источник — сообщение координатора/PR; receipt не выдуман. Codexremaining
перед контролем27%, account-wide; источник money/quota debit неизвестен.

Минимальный следующий шаг по новому поручению: заморозить совпадение именно
с заголовком профессиональной страницы; получить допустимый exact-URL target body
через native reader. Если адрес в поиске отсутствует, сопоставить raw HTTP search
payload с native message до изменения extractor или выбора другого транспорта.
Обычных collector-партий и третьих попыток прежних3 сегодня не будет.

Private immutable root: `enrichment-night-url-control-20261010` в прежней папке
экспериментов: manifest/seal до calls, старый reader отдельно, native raw,
search-client-result/selection, два reader outcome, robots, metrics-final,
offline-url-preservation и stopped.json. Public числовой документ byte-identical
private metrics-final. Исходники репозитория, старые roots/STOP и v6 метрики
не менялись. Для docs-only результата выполняются docs-check и независимая сверка
доказательств; актуальные CI/review/handoff публикуются в PR. #189 остаётся вне scope;
готовность к merge и продуктовая приёмка не заявляются.


## Direct HTTP 10.10: точный URL отвечает редиректом

Последний малый контроль по [поручению](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6090899434):
[plan до calls](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6090952234),
[безопасное уточнение до calls](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6090965443).
Зафиксирован exact `https://www.isir.upmc.fr/personnel/grossard`, anchors
Charline Grossard/ISIR и буквальный факт «Ingénieure de recherche».
Прежний MCP500/code1234 сохранён отдельной ссылкой/SHA как исторический исход.
Наследованные policy/native403/429 и persisted domain STOP для ISIR проверены
в19 roots; запрета не обнаружено. Старые roots/STOP не менялись.

Первый запуск композиции отклонён automatic approval review **до исполнения**:
configured mailto передавался бы во внешний User-Agent, разрешение на эту
метаинформацию не установлено. Исходные script/plan/seal сохранены неизменными,
физических HTTP calls этого варианта0. Выполнен допущенный безопасный вариант
того же HTTP пути: `SFRExperiment/2.0` без личного mailto, Settings/.env/auth/cookies.
Имя robots-агента прежнее; новый script/seal до calls, лимиты не изменены.
OpenAlex не вызывался. Это изменение отправляемой метаинформации, не обход
robots/403/429 и не смена сетевого сервиса.

| Операция | Exact URL | Ответ | Результат |
|---|---|---:|---|
| robots GET | https://www.isir.upmc.fr/robots.txt | 200, text/plain | 117 байт; путь разрешён, crawl-delay1s |
| HTML GET | https://www.isir.upmc.fr/personnel/grossard | 301, text/html | Location: https://www.isir.upmc.fr/personnel/grossard/; переход не выполнен |

Фактически2 HTTP requests, **1,216855 секунды**, follow_redirects=False/retries0.
Каждый запрос ограничен30 секундами total; robots64KiB, HTML2MiB. Статус301
остановил чтение на заголовках: body capture0bytes, complete=False.
SHA `e3b0c442…` относится к пустому **захвату**, не к телу целевой страницы.
Robots body SHA `5a729e512461ba914ae6bf7d2f053a5b64d61a6502c951d711c32d61ea3179e2`.
Ответ получен23:24:41UTC09.10 (02:24:41МСК10.10); даты HTTP проверок сохранены
в артефактах, дата информации о человеке не выводится.

Обычный HTTP подтвердил ответ на exact URL и канонический redirect с завершающим
слешем; **доступность target body не установлена**. Тело/статический текст/новые
доказанные цитаты/контакт не получены. SimpleHTML/extract не запускались на
redirect-body. Поэтому explicit conditional model gateFalse: GLM extractor0,
Sol0, Astra0; semantic packet не создавался и модельного receipt нет.
Идентичность, текущая аффилиация, дата/набор не оценены. Это диагностический
положительный случай, не новый профиль/prevalence/mixed12 и не третья попытка
последних3ID. Статусы фактов человека из этого исхода не выводятся.

Дополнительно проверен код native URL пути, без новых MCP calls:
`McpServerConnection.callTool` → `McpClient.callTool` → `validateCallToolResult`;
`McpClient.handleResponse` передаёт message.result; `StreamableHttpTransport.send`
и `consumeSse` разбирают JSON/SSE. Проверка content не преобразует link. Наш
`createSerializedTransport` сохраняет raw до readerView. Это кодовое основание
в пользу серверных значений link, а не локального обрезания URL; байтовый HTTP
search payload по-прежнему не сохранён. Ничего в parser не исправлялось.

Минимальный следующий шаг по новому поручению — закрепить **наблюдаемый** Location
`https://www.isir.upmc.fr/personnel/grossard/` и проверить его отдельным допустимым
ограниченным HTTP контролем. Третий запрос сегодня не сделан. Если body получен,
связь настоящего directHTTP source с действующей строгой quote-binding/PiCLI/Sol
цепочкой ещё требует проверки: текущий `enrichment_night.bind` принимает
успешные zai_reader events/MCP raw; directHTTP не выдаётся за такой receipt.
Существенной переделки схем/runner в этом контроле нет.

Счёт без новых content jobs:43 профильных+1 сообщённая архитектурная консультация
=44 зачтённых задания,15 новых людей,Astra4/4. Консультация backend/tokensunknown,
без выдуманного receipt. Последний известный remaining до этапа27% от координатора,
официальный usage после26%, account-wide; это не quota одного чата или HTTP debit.

Private immutable root `enrichment-night-direct-http-control-20261010`: original
и safer plan/seals/scripts, наследованный stop-check, request/response metadata,
bounded bytes/decoded captures, model gate, native code hashes, metrics-final и
stopped.json. Public numeric document byte-identical private. Использована лишь
одноразовая композиция существующих Budget/DomainStops/policy/httpx/extract;
полный benchmark run, Crawl4AI/браузер/поиск/HAL не запускались. Код репозитория,
прежние метрики/roots, продуктовые документы/паспорт не менялись. Проверки —
docs-check и независимая сверка артефактов; актуальные review/CI/handoff в PR.
#189 остаётся вне scope и препятствует готовности к merge; после передачи запись
исполнителя прекращается, дополнительных source/model вызовов нет.


## Canonical HTTP 10.10: тело получено, DirectHTTP binder ещё отсутствует

Последний контроль наблюдаемого Location по [поручению](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6091138109),
[freeze до calls](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6091160980).
В новом immutable root закреплён exact `https://www.isir.upmc.fr/personnel/grossard/`
из301 Location предыдущего контроля, со слешем. Это отдельный заранее разрешённый
контроль, не автоматический переход после301. Прежняя безопасная композиция
byte-identical: existing Budget/DomainStops/policy/httpx/extract/SimpleHTML,
SFRExperiment/2.0 без личного mailto/projectSettings/.env. Наследованные20 roots
проверены через raw/domain и batch stopped-domains; запрета ISIR нет.
Лимиты прежние: 2HTTP,30с/request total,robots64KiB/HTML2MiB,concurrency1,
без redirects/retries/search/browser/Crawl4AI/HAL. Старые roots/STOP не менялись.

| Операция | Exact URL | Ответ | Полный захват |
|---|---|---:|---:|
| robots GET | https://www.isir.upmc.fr/robots.txt | 200, путь разрешён | 117 байт |
| HTML GET | https://www.isir.upmc.fr/personnel/grossard/ | 200, text/html; charset=UTF-8 | 55 962 байта |

Фактически2GET, **1,454400 секунды**,0redirects/retries; HTML received
23:42:29UTC09.10 (02:42:29МСК10.10). HTML SHA
`bd35e105d6488881ee7845d086850b09fdfbc7905077b9eac4291e4fe65e0e3b`.
Static SimpleHTML text5241Unicode code points; original bytes/decodedHTML/text
сохранены раздельно, дата проверки не превращена в дату информации о человеке.
Оба frozen anchors Charline Grossard/ISIR и буквальное «Ingénieure de recherche»
присутствуют. Existing recover_quote подтверждает единственный непрерывный
фрагмент static-text[731:754] (zero-based/end-exclusive), без перевода/склейки.
Это механическая проверка заранее заданного факта, **не GLM extractor output**.

В именном блоке после этого факта есть один email-кандидат; ещё один относится
к общему footer. Значения/контактные spans только private. Новых семантически
принятых contacts/atoms0: личность каталога/текущая аффилиация/актуальность адреса
не проверены, наличие email не означает набор/готовность руководить.
Human_reviewed0; это положительный HTTP diagnostic, не новый человек,
прирост покрытия/prevalence/mixed12 или третья попытка последних3ID.

Body-conditionTrue, **existing strict binding-conditionFalse**. Точная недостающая
связь: `enrichment_night.bind` фильтрует только source_finished/kind=zai_reader/
outcomeok, затем читает raw_file.message.result.content и decoded url/content;
`enrichment_pi_pilot.validate_collection`/`bind_sources` требуют тот же reader
и resource_file. `prepare_control` принимает реальный collector output и уже
связанный evidence_pool, не удостоверяет приобретение HTTP-тела.
Нужен настоящий DirectHTTP source registry/adapter: exact URL,status/checked_at,
raw byte SHA,static text SHA и literal spans → строгая привязка цитат;
далее network-disabled PiCLI extraction и eligible packet/Sol. По условию
поручения новый adapter/schema не создаётся. HTTP-источник не выдан за
zai_reader/MCP receipt; фиктивного extractor/packet нет. Explicit model gate
фиксирует **GLM0/Sol0/Astra0**, новых model jobs0; содержательных продолжений нет.

Теперь доказана доступность **канонического адреса обычному статическому HTTP**.
Прежний MCP500 был для URL без слеша; MCP сcanonicalURL не повторялся.
Отличие адреса и транспорта не изолированы, поэтому нельзя объявить причиной
MCP500 один redirect или сделать вывод о качестве extractor. Repo parser не
чинится; следующее отдельное поручение — проверяемая DirectHTTP evidence binding
интеграция с сохранением source_kind/атрибуции и строгих отказов.

Счёт ночи прежний:43profilejobs+1 сообщённая consultation=44зачтённых задания,
15новыхлюдей,Astra4/4. Consultationbackend/tokensunknown, receiptневыдуман.
Последний remaining доэтапа25% откоординатора, официальныйtoolпосле24%,account-wide;
расход source money/quota unknown, HTTP не выдан за оплаченный modelAPI.

Private immutable root `enrichment-night-direct-http-canonical-20261010`:
manifest/seal/observedLocationSHA доcalls, наследованный stop-check,byte-identical
composition,2requests/responses/fullbytes/decoded/static extraction/text,
source-observations.private сoffsets/контактами, binding-gap сточнымифункциями/SHA,
conditional-model-gate,metrics-final/quota-note/stopped.json. Public numeric JSON
byte-identical private и не содержит email-значений/source bodies. Код repo,
старые метрики/roots и продуктовые документы/паспорт не менялись. Docs-check и
независимая docs-only сверка; актуальные review/CI/handoff — в PR. #189 отдельный
blocker; после передачи запись и собственные процессы остановлены.


## Дневной contact-first 10.10: три регрессии, свежий запуск заблокирован approval

[Постановка до calls](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6097281300),
[частичная обратная связь Бориса](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6097216802).
Новый ограниченный дневной проход; прежняя ночь, STOP, входы и результаты не
возобновляются. Три отзыва — качественный сигнал, не полный человеческий эталон.
Новая информация пользователя хранится отдельно; expected email/ручные вердикты
не добавлены в model-visible inputs. Известные положительные примеры — regression,
они не дают prevalence или оценку покрытия новых людей.

### Получение и привязка

Композиция существующих enrichment компонентов: SimpleHTML/extract, robots policy,
DomainStops/Budget, public_candidates/orcid_id, prepare_control/semantic-v3,
штатный PiCLI fallback и native Sol verifier. Production/каталог не меняются;
новых зависимостей/сервисов/фреймворка/биллинг-пути нет. Добавлен отдельный
`enrichment_contact_first.py` для bounded загрузки, code candidates и strict seals;
в существующем ORCID фильтре учитываются PUBLIC/public и только публичные links.

DirectHTTP имеет собственные URL/checked_at/status/raw-byte SHA/decoded SHA/text SHA,
registry path/SHA и точные Unicode offsets. Перед prepare и verifier bytes,
декодирование, SimpleHTML derivation, registry/receipt и literal spans сверяются;
готовым произвольным packet binder не обходится. MCP fallback перепривязывается
существующим MCP binder и сохраняет настоящий receipt; HTTP не выдаётся за MCP.
Code collector честно записывает model_called=false. Студентский набор не следует
из email. Дата HTTP-проверки не становится датой сведений о человеке.

Адрес Шумейко хранится в **параметре mail URL изображения** (`mail.php?mail=…`)
в исходном HTML; mailto отсутствует. Код разбирает тот же same-origin img attribute,
без загрузки изображения/OCR/угадывания/хардкода адреса. Полное тело7201байт,
static text829символов; имя, Бауман и предметный якорь присутствуют.
Статус аспиранта недатирован; актуальная должность и готовность брать студентов
unknown. Первый native Sol/high подтвердил принадлежность контакта.

ORCID ранний кэшируемый этап реализован через существующий structured parser,
публичные emails/researcher URLs остаются кандидатами. Live `pub.orcid.org/robots.txt`
вернул200/Disallow; API record GET **0**. Запрет сохраняется; для следующих профилей
использована та же проверка без новых robots-запросов. Это inaccessible, не отсутствие
контакта в других источниках. Качество нового live ORCID извлечения не измерено.
Публичные ссылки доступны в candidates для последующего ограниченного чтения;
автоматический неограниченный обход ссылок не добавлен.

Лимиты до calls:6HTTP/profile включая ORCID/robots/image,1robots/host/attempt,
2HTML/attempt,1observed image,30s total/request,64KiB/2MiB/1MiB,
concurrency1/delay≥1s,redirects/retries0. No .env/Settings/private mailto/cookies;
client trust_env=false. HTTP403/429 и Disallow останавливают источник.
Первый inherited check ошибочно искал config.json вместо batch.json; исправление
сохранено отдельным artifact:20roots/96настоящих batches проверены,
активные четыре домена не имели унаследованного STOP. Старые roots не изменялись.

### Регрессии и конкретные исправления

| Фиксированный профиль | Полное HTTP тело | Code candidates в конечном packet | Подтверждённые контакты |
|---|---:|---:|---:|
| A5068285041 Шумейко |7201байт|1|1|
| A5026442137 Пархомчук |13129байт|1|1|
| A5061174451 Знаменская, сотрудники кафедры |38783байта|8|1|

У двух сайтов robots404 ошибочно блокировал HTML. По
[RFC9309§2.3.1.3](https://www.rfc-editor.org/rfc/rfc9309.html#section-2.3.1.3)
в новой композиции разрешён только404 как отсутствие robots;
301/401/403/429/5xx/обрыв и200Disallow сохраняют отказ. Статус не подменяется200.
[Конкретный fix и единственный повтор loading stage](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6097392011)
в новых attempt2 roots. Личная страница Знаменской затем далаHTML404;
[второй отличный known URL из отзыва](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6097429402)
(сотрудники кафедры) дал200. Всего по Знаменской4HTTP включая первую robots-ошибку,
по Пархомчук3,по Шумейко3; общий потолок6/profile не увеличен.

Проверка кафедрального body выявила CRLF: read_text нормализовал переносы и
нарушал SHA. Исправлено чтение UTF-8 bytes без нормализации; packet восстановлен
offline из тех же saved bytes, HTTP0. Первая Sol Знаменской отвергла все8кандидатов:
отдельный mailto не сохранял именную HTML-связь. Адрес из человеческого отзыва
фактически уже был извлечён, лимитом не отсеян. Минимальный fix сохраняет только
непрерывное HTML окно700символовперед/500после атрибута плюс отдельный static context.
Ни склейки, ни ожидаемого вердикта. [Повторная verifier стадия2/2](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6097493246)
в новом root: Sol подтвердил один контакт, семь чужих остались отклонёнными.
Других попыток нет; первые inputs/results сохранены.

Итог известных примеров:3/3контакта supported полной Sol/high, identity отдельно
поддержана, нынешние аффилиации/индивидуальные даты не равны каталожным или
общему обновлению сайта. Актуальность email человеком не удостоверена;
готовность/набор студентов не установлены. Результат модели не человеческий gold.
На кафедральной странице код видел16distinctemails, packet ограничен8;
контексты≤20000символов/source. Это не исчерпывающая экстракция.
Доля без агентского поиска **3/3** только на этих заранее знакомых примерах.

### Свежая выборка и точный blocker

Кодовый freeze `a045eccdee696ab9986034ef79a643267bffd1b8`,
[10 ID и критерии до live](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6097528437):
10разныхвузов,seed19319420261010,140исключённыхID, SHAsample/index/DB/code/rules.
Первый `A5070748575` (Salman Ahmadi‐Asl, Автономная некоммерческая организация высшего образования Университет Иннополис).
Запланировано1→3суммарно→до10 при подтверждённом источнике/контакте;
первыйнеуспех→конкретныйfix+одинновыйrootrepeat, остальныхнежечь.

Свежие profiles **0/10**, GLM **0**: первый штатный PiCLI/GLM5.3Flash/high
fallback не был исполнен. Automatic approval review отклонил payload/destination
и расход подписки до процесса. Проверка исходного native userMessage Бориса
«ок. что дальше?» после явного плана GLM/10новых также не была принята как
достаточное явное согласие на передачу конкретного профиля/текста в api.z.ai.
Вторая проверка разрешений тоже отклонила тот же action до исполнения;
обхода, другого транспорта или дальнейших повторов нет. Для live нужны явное
разрешение на public profile payload → existing api.z.ai подписку и новый root;
нынешний fresh root STOP. Его frozen manifest относится к a045ecc; позднейшие
STOP-guards требуют нового code freeze при будущем разрешённом запуске.

Fallback подключён к существующему PiCLI,4search/8resources/6requests/600s,
без увеличенияcaps. Новый ограниченный deadline принимается только новым
contact-first root без STOP, совпадающим с manifest; старые ночные deadline
не изменены. Live fallback не проверен. GLM/MCP source binding и DirectHTTP
имеют разные реальные acquisition chains. Пустой packet не расходует GPT.
Новые source/GPT jobs из STOP root запрещены; cached sources читаются offline.

### Фактические расходы, проверки и ограничения

День: **10HTTP** (6robots/4HTML,recordORCID0/image0), download-only
7.132871s (rate waits и время разработки отдельно, полного pipelinewalltime нет).
**4Soljobs** (3первичные регрессии+один verifier repeat), input81099/output10139,
итого**91238tokens**; reasoning2793 — subset output, не добавлен к total.
Sol walltime **281.875112s**. GLM/jobs/search/tokens0,Astra0; subscription debit,
денежный debit источников и GLM balance unknown, API-цены не подставлены.
Все Sol запросы6.1/high с полной прежней инструкцией/strict semantic-v3 schema,
tool-less/MCP-disabled; фактический undisclosed backend не выдуман.
Ночь остаётся44(43profile+1consultation),15новыхлюдей,Astra4/4;
день считается отдельно, новыхлюдей0. Официальный Codex remaining20%вначале,
19% передпоследнимэтапом,account-wide; threshold15% не достигнут.

Python lint/typecheck/test PASS: 233unittest,388pytest/8skip/5deselect,
coverage94,06%;16новых офлайнтестов на URI candidates/cache/SHA/CRLF/STOP/quota/
404-vs403429/non200/повторныеreservations/daydeadline/inputtampering.
Strict audit FAIL только deps-node/fs-trivy, прежние HIGH sharp/source-map-js
(#189 вне scope). Требования и зависимости не ослаблены. Node26.8.2/Pi1.1.0
установлены; CLI GLM не запускался. Web source не менялся; currentCI/review/handoff
в PR отдельно после финального commit.

Один ранний test-final.log случайно перезаписан финальной проверкой;
source bytes/text,inputs/results/receipts и числовые измерения не изменены.
Исходный metrics-final сохранён с прежним hash этого журнала; отдельный erratum
и v2 меняют только verification log fingerprint. Оба numeric snapshots сохранены,
[актуальная версия](enrichment_contact_first_20261010.metrics.v2.json) byte-identical
private. Проверка source/model SHA остаётся полной; исходные bytes раннего testlog
не восстановлены. Прежние ночные roots/снимки не затронуты.

Private roots `enrichment-contact-first-20261010` и
`enrichment-contact-first-fresh-20261010`: scope/seals/feedback separate,
regression source bytes/registry/statictext,actual Sol receipts/inputs/outputs,
partial/recovery results,metrics-v1/v2/erratum,code/sample freeze/approval rejection,
STOP и checks/review/CI/transfer evidence. Контактные значения/source bodies только
private. Это ограниченный технический результат с approval blocker,
не измерение покрытия fresh10 и не завершение #193/#47/#103.
Production/product docs/passport, merge/deploy/main push не выполнялись.

Независимый дневной reviewer проверил e4e9539 и подтвердил один Medium blocker:
STOP общего root не распространялся на новый вложенный model/fallback root.
Фактических запусков после STOP не найдено. Исправление объединяет ancestry
проверку HTTP, Sol и Pi collector до Batch/workspace/process; офлайн regression
проверяет child-root для всех трёх путей. Новых live/source/model jobs нет.
Повторное ревью исправления и CI окончательной версии фиксируются в PR.
Ревью сверило 169 SHA v2 и 22 literal spans четырёх входов Sol. Сохранённый
gitleaks history log с 0 commits не доказывает проверку истории; staged hook
и актуальный CI рассматриваются отдельно. Legacy диапазон PR до c83fb35
полностью повторно не ревьюился; готовность всего PR не заявлена.

## Разрешённый свежий contact-first контроль 10.10: first-profile gate STOP

Этот раздел продолжает только ранее заблокированную frozen десятку. Прежний
дневной regression результат, numeric v1/v2/erratum, старые inputs/STOP
сохранены без изменений. Прямое native human разрешение Бориса на публичные
данные этих10ID → Z.ai/Pi по существующей GLM подписке и новый quota stop5%
зафиксировано [в PR](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6097877495).
Платный API billing, покупки/reset-credit, новые аккаунты и Astra исключены.
Новый immutable top-level root и [freeze до вызова](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6097905660)
используют тот же sample SHA `07cc9fd0fcdfe7b4ad1847bbd8d6c6de4840f735b75fabe2ae7e5b2bfba3e387`,
10ID из10вузов, прежние критерии и code freeze `e266bf3b43da3ba8841d49a59f22252573e8aaa8`.
Порог нового запуска читается из frozen manifest:5%, legacy/default остаётся15%.
Новый offline fixture проверяет5%/NaN/invalid threshold STOP и default15%.
Предел30 дневных профильных model jobs начинает с4 исполненных regression Sol;
прежние два approval denial до исполнения не считаются jobs. Новых отказов
разрешений при нынешних двух запусках нет. Старые roots не возобновлены.

Первый и единственный новый человек — A5070748575, Salman Ahmadi‐Asl.
Early source stage: известных author URLs в каталоге нет, ORCID API остаётся
закрытым saved current-day robots Disallow; record API GET0. Это не вывод об
отсутствии публичного контакта. GLM collector — штатный Pi/GLM5.3Flash/high,
полная прежняя Sol6.1/high инструкция сохранена, но пустой пакет не расходует GPT.

### Две попытки первого collector; остальные9 не запускались

Первая попытка: один GLM job,4 model request config receipts /3 actual chat HTTP
metadata, один поиск,0 host robots/reader source calls. Private runner автора
не имел main guard. При multiprocessing spawn host policy worker импортировал
runner и повторно выполнил quota write; immutable artifact отличался и worker
завершился без результата. Не было повторного GLM job внутри worker: отказ
случился до collector invocation. Pi завершён exit143, model_completed=false,
usage incomplete, partial/receipts сохранены, root STOP. Это ошибка оркестрации
автора, не ошибка источника и не отсутствие контакта.

Конкретное исправление: main guard только в новом immutable private runner.
Офлайн импорт с `run_name=__mp_main__` подтвердил0 collector/verifier calls и
отсутствие quota/action writes. Рубрика, binder, extractor и измерители не менялись.
[Единственная разрешённая повторная попытка](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6097926772)
в новом top-level root, attempt2/2; исходный общий35min deadline не продлён,
прежние4search/8resources/6requests/600s сохранены.

Retry: один GLM job /5 configs и5 actual chat HTTP metadata, один поиск,
0 host robots и0 reader source calls. Search вернул6 точных ссылок. Collector
выбрал ORCID URL, отсутствующий в allowed exact links сохранённого search
ответа; policy отклонила URL до host/reader reservation. Дополнительный search
был отклонён read-now gate при наличии discovered links. Первый search с
нормализованным дефисом тоже был отклонён до сети: frozen basic query должен
совпадать буквально; следующий exact query выполнен. Эти denials не source calls.
Search snippets не использованы как доказательства. Collector завершён exit0,
model_completed=true, но normalized eligible packet содержит0 items/0 evidence.
Источник/контакт содержательно не подтверждены, поэтому gate1→3 не пройден.
Sol не запускался; третьей попытки, нового исправления во время прогона или
другого транспорта нет. Retry root STOP, остальные9 не запускались.

### Измерения и границы результата

[Актуальный числовой артефакт](enrichment_contact_first_fresh_20261010.metrics.v2.json)
byte-identical private `metrics-fresh-v2.json`; исходный v1/217 SHA сохранён,
v2 добавляет SHA erratum и оригинала (219refs). Числа получены из actual
receipts/status/HTTP metadata. Fresh:1 уникальный
профиль из10 frozen,2 GLM collector jobs,9 request config receipts и8 actual
chat HTTP metadata,2 search calls,source reads/host robots/direct source HTTP0,
Sol/Astra0,confirmed contacts/source rows0. Это1 attempted case, не coverage,
prevalence или accuracy каталога; невозможность пройти acquisition gate не
означает отсутствие контакта у человека. Agent-free contact fraction unknown:
0 найденных контактов, знаменатель0. Identity/currentness/recruitment не установлены.

У первой partial попытки сохранились7970 tokens завершённых сообщений;
полная стоимость/usage неизвестна. У retry complete usage27391 tokens.
Вместе наблюдалось35361 tokens: input20624,output3857,cacheRead10880;
reasoning3211 уже входит вoutput. Это incomplete lower bound, не полный debit:
незавершённые сообщения первого collector не превращены в нули и не добавлены
по guessed snapshots. Collector wall22.225943+85.709339=107.935282s; полного
pipelinewalltime с разработкой/ожиданием нет. Actual model/effort/backend в
receipts undisclosed; requested configs GLM5.3Flash/high зафиксированы.
API price/subscription balance/debit не выдуманы.

Сохранено30 Z.ai HTTP metadata:12 search-MCP,10 reader-MCP,8 chat. MCP числа
включают initialize/list/transport/cleanup, не30source calls. Два405 на root
MCP transports в каждой попытке не относятся к robots/источникам. Caps соблюдены:
по одному выполненному search на collector,0readers/robots,4и5 model configs≤6,
22и86s≤600. День теперь6 исполненных profile model jobs (4known Sol+2freshGLM),
наблюдаемых GLM chat HTTP metadata8. Число физических HTTP Sol неизвестно:
четыре Sol jobs не раскрывают provider transport/retries и не складываются с
HTTP записями GLM. Общий физический HTTP count моделей unknown.
Ночь44/15/Astra4 прежняя отдельно.
Официальная квота Codex18% перед первым запуском,17% после содержательного
этапа,account-wide; новыйstop5% не достигнут. Human feedback прежняя частичная,
fullgold0; oldhuman_reviewed0 не переписан.

Для quota code change: lint/typecheck/test PASS,234unittest/388pytest,
coverage94,06%. Strict audit снова FAIL только прежний#189 deps-node/fs-trivy
sharp/source-map-js; критерии/зависимости не ослаблены. Docs-check, независимый
review/currentCI/handoff окончательного report commit фиксируются в PR;
зелёная готовность к merge не заявлена. Новых интеграций/библиотек/профилей нет.
Паспорт/product docs/production/main/merge/deploy/global config не менялись.

Private roots `enrichment-contact-first-authorized-20261010` и
`enrichment-contact-first-authorized-retry-20261010` сохраняют direct human
permission, sample/code/runner freezes, raw events/requests/responses,
receipts/partial/empty packet, guard test/diagnosis, STOP, checks/review/CI
и финальный SHA index. Первоначальные regression и blocked fresh roots
остаются отдельными STOP. Результат — проверяемый первый acquisition gate failure;
это не завершённый fresh10 и не доказательство готовности масштабировать каталог.

Независимый fresh reviewer проверил b907152 и подтвердил один Medium blocker
атрибуции: original numeric v1 ошибочно обозначал4Soljobs+8GLM HTTP как12
известных upstream HTTP. Выпущены отдельные immutable erratum/v2: observed
GLM HTTP8, Sol physical HTTP и общий физический model HTTP count unknown.
Исходный v1 сохранён byte-for-byte; его ошибочное поле нельзя использовать.
Остальные source/job/token/time/gate числа и217 исходных SHA не изменены;
новых содержательных jobs нет. Reviewer подтвердил217 новых и169 прежних SHA,
оба runner/sample/code freeze, два first-profile attempts и STOP остальных9.
Повторное review/CI/handoff исправления фиксируются на окончательном head в PR.

### 10.10: точные ссылки reader и один следующий frozen профиль

Поручение и граница проверки — [комментарий PR194](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6099201308).
После офлайн-разбора разрешён только следующий A5047877230 из прежних frozen10:
один collector, полная прежняя Sol/high только при непустом допущенном пакете.
Остальные8 не запускались, A5070748575 третьей попытки не получил.
Исчезнувший собственный temporary checkout восстановлен из сохранённого f9cd0ef;
primary main и чужое удаление CLAUDE.md не менялись. Координатор пока прочитал
outputs/артефакты; независимые локальные SHA/handoff им не повторены из-за
CreateProcess os error2. Техническое восстановление не заменяет продуктовую приёмку.

**Причина прежнего отказа.** Saved native search возвращает шесть `row.link`
только на корни сайтов. Выбранный полный ORCID URL совпадает с frozen catalog
ORCID; его идентификатор встречается в snippets, а полного URL в response нет.
Выбранный URL не совпадает с точными ссылками поиска. Модель видела
double-encoded исходный результат и host список exact URL. Это смешение якоря
личности с provenance поиска; считать сам ORCID выдуманным оснований нет.
Exact-match отказ был корректен. Existing extension теперь передаёт native
reader enum точных unused URL, не подставляя/не нормализуя пути. При отказе
показывает допустимые ссылки; search временно скрыт при unread links без
содержательного тела. При неверной схеме инструмента — fail closed.
Host reservation, STOP, robots, caps и literal binder сохранены.

Офлайн replay actual saved response проверяет прежний отказ и следующий exact
URL без сети/модели. Новые тесты проверяют catalog/snippet substitution,
различия scheme/trailing slash, неизменность payload/budget, отсутствие
source reservation при отказе, последующее разрешённое чтение и STOP транспорта.
Private runner импортирован как `__mp_main__` без аргументов: collector/verifier
calls0 и action/quota writes0. Freeze: **91bade4aa555e1988a789b2f4a8fcf7ee00a60f8**,
тот же sample SHA `07cc9fd0fcdfe7b4ad1847bbd8d6c6de4840f735b75fabe2ae7e5b2bfba3e387`.
Новый private root `enrichment-contact-first-exact-links-20261010` отдельный;
его runner допускает только A5047877230, один collect и максимум один verify.
Ранний этап: target author URL в frozen каталоге отсутствует; сохранённый
current-day robots200/Disallow проверен по SHA и применён к точному ORCID API
record URL. Direct HTTP0, ORCID API GET0; запрет не обходился.

**Live результат — gate FAIL.** Один GLM collector штатно завершился.
Один выполненный search снова дал корни сайтов. Два exact reader URL приняты,
host robots2 и reader2 выполнены: главная ВШЭ (10228 chars) и ACM challenge
«Just a moment…» (257 chars). Обе страницы проходят технический минимум
длины/слов, но он не подтверждает target identity/полезность источника.
Единственная raw цитата об организации ВШЭ не совпала дословно с сохранённым
reader body: `quote_not_literal_or_unread`. Candidate/rejection/source сохранены;
допущенные quotes/items/profile refs0. Identity/contact/currency/recruitment
unknown, information_date null. Пустой пакет не передавался Sol. Принятый URL
и общая главная страница не выполняют критерий target-source + literal quote.

[Числовой snapshot v2](enrichment_contact_first_exact_links_20261010.metrics.v2.json):
28026 tokens complete (input23961, output2593, cacheRead1472, cacheWrite0;
reasoning2083 — часть output, не дополнительное слагаемое), collector79,955410с,
host stage80,042890с. Пять model-request configs/пять chat HTTP200;
13 MCP HTTP metadata включают handshake/cleanup и не являются13source calls.
Source calls: search1, reader2, host robots HTTP2; early directHTTP0.
Requested Pi/GLM5.3Flash/high по существующей подписке; actual model/effort/backend,
денежный debit и subscription quota delta не раскрыты. Новых Sol/Astra0;
день7profile jobs (прежние4Sol+2GLM и этот1GLM), cap30 не сбрасывался.
Официальный Codex remaining16% до/после измерения, новый stop≤5% не достигнут.
Это отдельный человек, не A/B предыдущего случая и не измерение fresh10 coverage.

Original числовой snapshot сохранён; v2/erratum исправляют только технический
body counter1→2 по финальному request5 receipt. Эти две страницы остаются
неподтверждёнными источниками для человека. Все source/model данные, gate,
quotes/contact/token/time/job числа прежние. Offline diagnosis v2 также
уточняет имя существующего request4 config вместо ошибочной ссылки v1;
исходный diagnostic файл сохранён. Diagnostic v3 уточняет, что в snippets
найден идентификатор ORCID, а полный URL — только в каталоге; прежние diagnostic
файлы и измерения сохранены. 248 прежних private SHA перепроверены без
изменений. Новый root имеет STOP; повторов, остальных8 и третьей попытки первого
профиля нет. Более широкий запуск остановлен.

Локальные lint/typecheck/test PASS:234unittest,388pytest,coverage94,06%; Node25/25,
docs-check PASS. Initial strict audit потребовал восстановления node_modules
из lock; полный повтор и актуальные CI/review/handoff фиксируются в PR.
Следующее решение: сначала выяснить по штатному search contract/raw, почему
приходят корни сайтов и можно ли получить точные target URLs; отдельно остаётся
ошибка literal quote. Дальнейшие live profiles/framework/API в это поручение
не входят. Product docs/паспорт/production/main/merge/deploy не менялись.

### 10.10: офлайн-локализация root-only search и metadata quote

[Следующее поручение PR194](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6100035162)
разрешает локализацию цепочки URL и цитаты; reserve5% отменён Борисом для этого
цикла («квоту можно жечь в 0»), до фактического отказа подписки без покупки,
reset-credit, смены аккаунта или обхода429. Native human turn/message IDs сохранены.
Текущий clean code freeze650029d, baseaccc508cd398b5e57105fe1c45f906f89330d636
подтверждены API; единственный writer этой копии — техническая сессия.
Продуктовый координатор прочитал outputs; независимые локальные SHA/handoff
им не повторены. Новый immutable root `enrichment-search-contract-offline-20261010`,
прежние184SHA и STOP перепроверены без изменений.

**Точный путь не теряется локально.** Saved native RPC двух успешных поисков
и actual `tool_execution_end` сопоставлены по текстовым bytes, а не по display.
Установленный Pi1.1.0 `parseJsonRpcMessage` возвращает исходный объект;
JSON/SSE transport не переписывает поля result. Offline replay actual saved RPC
через этот parser и `convertMcpResult` совпал с записанным model tool-result.
SSE framing в replay синтетический; исторический HTTP wire body не был сохранён.
Это не новый сетевой захват. Уже сохранённых RPC + прозрачного parser + actual
model-result достаточно установить отсутствие локального path stripping;
диагностический live search не понадобился.

| Этап / точное поле | A5070748575 | A5047877230 | Проверенный вывод |
|---|---|---|---|
| Saved native `result.content[0].text` после двух JSON decode | 6 rows, только `title/link/content/refer` | 4 rows, те же поля | В самом возвращённом result нет отдельного document URL |
| `row.link` | `https://orcid.org`, `https://www.wikidata.org`, `https://epubs.siam.org`, `https://link.springer.com`, `https://iopscience.iop.org`, `https://www.researchgate.net` | `https://www.hse.ru`, `https://researchlink.ardc.edu.au`, `https://dl.acm.org`, `https://status.researchdata.ardc.edu.au` | Все10 links — корни без пути/query/fragment |
| `row.url`, structured `row.metadata` | Поля отсутствуют | Поля отсутствуют | Нет пропущенного alternate URL field; snippet anchor не document URL |
| Native parsing → model tool-result | Text bytes равны saved RPC, без truncation | То же | Путь не удаляет ни native parser, ни model conversion |
| Registered links до попытки reader | Ровно6 `row.link` | Ровно4 `row.link` | Snapshot3 перед первым чтением ВШЭ — уже после маркировки выбранного URL attempted; четвёртая ссылка не потеряна |
| Выбранный reader URL | Catalog ORCID path отсутствует в `row.link`, отказ | Два roots: ВШЭ/ACM, exact accepted | Exact selection не восстанавливает отсутствующий адрес человека |

Фактический input проверен по saved `tools/list` и разрешённому `tools/call`,
не по памяти документации. Tool name `web_search_prime`, required `search_query`,
пять properties: query, domain filter, recency filter, content size, location;
`additionalProperties:false`. A507: frozen имя/full ORCID URL, location`us`,
content_size`high`. A504: frozen имя/full ORCID URL, location`cn`, content_size
не передан (schema default medium). Оба возвращённых результата root-only;
это разные люди, не A/B параметров. `content_size` описывает длину summary,
`location` — регион, не точность URL. Неиспользованного output/URL-precision
переключателя в фактической схеме нет.

[Официальная subscription MCP документация](https://docs.z.ai/devpack/mcp/search-mcp-server)
описывает title/URL/summary и совпадающий endpoint, но не гарантирует глубинный
person/document URL и не документирует recovery mode. Название `webSearchPrime`
на странице отличается от фактического tool ID; использовался сохранённый ID.
[Standalone Web Search API](https://docs.z.ai/api-reference/tools/web-search)
— другой endpoint; его `search_engine/count` нельзя переносить в установленную
MCP schema или считать разрешённой заменой транспорта. Этот API не вызывался.
[FAQ](https://docs.z.ai/devpack/faq) связывает модели/MCP с credits подписки;
текущий остаток Z.ai credits неизвестен. Внутренняя причина upstream root-only
не установлена; доказано отсутствие target URL именно в этих двух ответах,
без утверждения, что любой запрос сервиса всегда возвращает корни.

**Причина quote rejection — неверное представление источника.** Единственная
цитата ВШЭ дословно совпадает с `reader.description`, двумя элементами
`reader.metadata.description`, `og:description`, `mrc__share_description`,
`twitter:description`: шесть точных мест. В `reader.content` её нет, нет и в
search snippets. В показанном модели reader description цитата сохранена;
body10228chars показан целиком, `model_view_truncated:false`. Это не выдуманный
текст, не whitespace/обрезка и не цитата другого прочитанного сайта. Модель
использовала description/metadata вместо допустимого body. Source — общая
страница организации; metadata `og:url=https://www.hse.ru/en/` также не адрес
учёного. ACM challenge не источник факта. Строгий body-only binder отклонил
цитату корректно; метаданные не переименованы в body и не склеены с его строками.

Офлайн проверки: два actual saved cases/10rows, native JSON parser, synthetic
SSE framing, conversion→actual model-result equality, точное registered set;
fixtures root-only/exact URL with query/double JSON/metadata-vs-link/empty/error.
Replay запрещает fetch и зафиксировал network attempts0. Никаких source/model
jobs для ожидания или диагностики нет. [Числовой snapshot](enrichment_search_contract_offline_20261010.metrics.json):
diagnostic search0/reader0, newGLM/Sol/Astra0, profiletokens0, день по-прежнему7/30.
Documentation web reads отделены от subscription MCP diagnostic calls;
разработка/ревью не названы profile jobs и их token total не измерен.
Official Codex remaining перед этапом15%, reserve0. Старые thresholds5/15 в
замороженных прежних manifests остаются историей, не текущим разрешением.

**Блокер и решение.** Малой подтверждённой локальной потери URL нет;
документированной малой поддержанной настройки recovery не найдено.
Условие нового A5006480668 поэтому не выполнено: он не запускался, первые2
не повторялись, остальные8 не запускались. Root STOP. Для продолжения нужен
reproducibility packet провайдеру штатного subscription MCP и подтверждённый
способ вернуть exact document URLs; сообщения провайдеру здесь не отправлялись.
После исправленного native ответа — offline replay без угадывания путей,
затем один новый immutable A500 контроль:≤1GLM job,≤1fullSol только nonempty
eligible packet,4search/8resources/6modelrequests/600s/direct≤6HTTP. День7/30,
максимум23 свободных jobs до других исполнителей; этот контроль максимум2,
остаток credits неизвестен, при фактическом отказеSTOP безпереброса billing.
Если провайдер не даёт document URLs, конкретная отдельная альтернатива —
ограниченное извлечение реально наблюдённых navigation/person-directory links
из сохранённого HTML с frozen frontier, source budget и identity evidence;
новое поручение нужно до live реализации такого метода. Scrapy/Crawl4AI,
другие поисковые сервисы/платные endpoints не добавлены.

Код/измерители не изменены: нужны docs-check с actual meta, независимое ревью
этой диагностической дельты и CI/handoff актуального head, без повторного
полного code test suite. #189 вне scope, audit не ослабляется. Product docs,
паспорт/main/merge/deploy/globalconfig не менялись; полезный сбор по-прежнему
не доказан и техническая достоверность не заменяет продуктовую приёмку.

### 10.10: ограниченный проход по наблюдаемым href ВШЭ

[Новое поручение до source calls](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6100274477):
root → HTML href → каталог/персональная страница, максимум2перехода и6новыхHTTP
includingrobots, concurrency1,30s/request, robots64KiB/HTML2MiB, без
redirects/retries/LLMplanner/JSbrowser/OCR/новых библиотек. Новый private root
`enrichment-observed-links-hse-20261010`. Baseaccc/head854fa3b подтверждены API,
собственная ветка clean, другого writer в этом checkout нет. Цель — A5047877230
из прежнего frozen sample; имя/ORCID/публикационные якоря сохранены без ожидаемого
email. Не новый профиль и не collector attempt#3. GLM/Astra0; максимум1полный
Sol6.1/high только при полученной person page с предметными identity anchors
и буквальным контактом. Reserve0 до фактического отказа, без покупок/reset/обхода.

Saved reader content сначала прочитан офлайн через HTMLParser: actual `<a href>`0.
Это Markdown с текстовыми ссылками, не исходный HTML; metadata не авторизуют
неизвестный URL. Поэтому использовано разрешённое исключение — один direct
HTML GET exact `https://www.hse.ru`, дословно из saved search/reader, после fresh
robots. Frozen runner SHA и source module SHA, профиль и source SHA записаны
до calls. Существующий `Loader.load` переиспользован с private diagnostic request
adapter: root+2observedHTML допустимы до3HTML, общий бюджет6; старые collector
лимиты не менялись. HTTP receipts/body сохраняются прежним способом внеgit;
headers/credentials не экспортируются. Поиск/reader MCP не вызывались.

| Физический новый запрос | HTTP | Полное тело | Результат |
|---|---:|---|---|
| `https://www.hse.ru/robots.txt` | 200 | 3412bytes | Root разрешён для прежнего SFRExperiment user-agent, Crawl-delay3 соблюдён |
| `https://www.hse.ru` | 302 | Нет; savedbytes0 | Redirect не переходили, retry нет; actual HTML не получен |

**До href/целевой страницы не дошли.** Non200 body не сохраняется действующим
bounded loader; `Location` также не захвачен, конечный адрес неизвестен и не
угадывается. Это HTTP302, не ошибочно названный403/CAPTCHA или quota отказ.
Сетевой проход остановлен после2/6HTTP, link transitions0/2; нет основания
использовать остаток бюджета на произвольные пути или повтор root. Inherited
domain-stop scan пяти прошлых contact roots не обнаружил domain bans; старые
job STOP не снимаются и не превращаются в новый live run. ACM не трогали.

Person HTML0, предметные identity evidence0, буквальные контакты цели0;
GLM/Sol/Astra jobs0, profiletokens0, день остаётся7/30. Sol не вызван из-за
отсутствия допустимого материала; output/receipt/verdict модели не выдуманы.
Official Codex remaining14% после прохода совпадает с переданным координатором
remaining14%, account-wide; затраты разработки/ревью не измерены как profilejobs.
HTTP latency sum и исходные секунды — в [числовом snapshot](enrichment_observed_links_hse_20261010.metrics.json);
общий wall неизвестен и не заменён суммой latency. Root STOP; остальные8/A500
не запускались. Полезный результат отсутствует, поэтому переиспользуемая
link-discovery функция в коде репозитория не оставлена: private diagnostic
runner сохранён с измеренным SHA, без заявления о работающем crawler.

Пять meaningful offline MockTransport проверок PASS: дословный starttag/href,
anchor/parent/sourceSHA и отказ чужогоhost/изменяющего basehref; redirect без
followup/retry; bounded body отказ;6HTTP/3HTMLbudget до сети; root STOP/domain403
до сети. Дополнительных реальных HTTP0; actual measurement неизменён. Предыдущие
23sealedSHA офлайн-диагноза854 повторно совпали, его результаты/STOP сохранены.

**Одна конкретная альтернатива:** отдельно разрешить новый ограниченный проход
с максимум одним университетским redirect от exact root. Сначала сохранить
дословный `Location`, закрепить observed destination, проверить его robots,
только затем GET; без guessed paths/цепочек redirect, прежних403/429/login/
CAPTCHA обходов и новых сервисов. Общий HTTPbudget обязан включать root302,
destination robots/HTML и последующие переходы; два href-перехода остаются
отдельным лимитом. Это изменение текущего no-redirect разрешения, здесь оно
не реализовано и не выполнялось. Вузовский catalogue/API в HTML не наблюдался,
поэтому его наличие или конкретный путь не заявляются.

Изменения в git только документов: отчёт и новый numeric snapshot. Нужны
docs-check с actualmeta, независимое ревью новой дельты и актуальные CI/handoff;
полные кодовые проверки повторно не запускаются. #189 вне scope, критерии audit
не меняются. Product docs/паспорт/main/merge/deploy/globalconfig не менялись.


## Разрешённый redirect ВШЭ, затем общий эксперимент на десяти профилях

После отдельной [постановки](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6100428201) выполнен новый диагностический проход того же A5047877230. Его [числовой snapshot](enrichment_validated_redirect_hse_20261010.metrics.json) побайтно перенесён из отдельного private root `enrichment-validated-redirect-hse-20261010`; прежний no-redirect результат не изменён. Исходный код — d09c420, четыре новых HTTP и ни одного профильного задания модели.

Fresh robots разрешил корень, точный `Location: /en/` дал английскую главную страницу. Из её настоящего HTML выбран Staff Directory, затем сохранён каталог с 1549 href. Имя целевого человека в полученном каталоге отсутствует; это не доказывает отсутствие сотрудника в университете. Следующий буквальный href `?ltr=S;udept=22726` запрещён применимой wildcard-строкой robots `Disallow: /*r=`: она совпадает с `ltr=`. Запрос к запрещённому URL не отправлялся. Первоначальный выбор footer с HTTP исправлен до GET; обе записи исхода сохранены. Получены две полные HTML-страницы, один обычный redirect и один завершённый href-переход, контакта и подтверждённой личности нет. Root остановлен, 44 файла зафиксированы отдельным SHA-индексом.

Этот диагностический этап не передавался отдельно: до обновления документов Борис разрешил закончить один полезный эксперимент на прежних десяти, самостоятельно выбирая доступный метод для каждого человека. Новая [постановка до вызовов](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6100527186) снимает прежние промежуточные gates и искусственные ограничения навигации. Robots, CAPTCHA, login, paywall и реальные 403/429 остаются границами доступа.


## Итог гибкого сбора на прежних десяти, 10 октября 2026

**Получен полезный ограниченный результат:** 10/10 профилей имеют сохранённые первичные материалы и полную проверку semantic-v3; для 8/10 подтверждён личный контакт. Из восьми адресов три исторические и пять недатированные. Текущая доставляемость email не проверялась. Агентская оценка подтверждает личность для 10/10 и нынешнюю исходную аффилиацию для 5/10; готовность принимать студентов неизвестна для всех десяти. Это покрытие контактных кандидатов после проверки, не человеческая precision/recall и не оценка полноты всех 18 полей.

[Числовой snapshot](enrichment_flexible10_20261010.metrics.json) создан из неизменяемых результатов и перенесён побайтно. Выборка сохраняет SHA `07cc9fd0fcdfe7b4ad1847bbd8d6c6de4840f735b75fabe2ae7e5b2bfba3e387`. Новый private root — `/Users/boris/Experiments/search-for-research/enrichment-flexible10-20261010`; входы, raw replies, HTTP ledger, native receipts, `per-profile-review.json` и `review-cards.html` остаются вне git. Человеческих решений и gold — 0.

| Профиль | Источников | Личных контактов | Применимость контакта | Личность | Нынешняя аффилиация |
|---|---:|---:|---|---|---|
| Salman Ahmadi‐Asl | 3 | 1 | historical | подтверждена | подтверждена |
| Evgeny Styrin | 3 | 0 | не установлен | подтверждена | подтверждена |
| О. В. Тушавина | 2 | 1 | historical | подтверждена | не установлена |
| Alena Nastulyavichus | 2 | 1 | undated | подтверждена | не установлена |
| И. В. Морозов | 2 | 1 | undated | подтверждена | подтверждена |
| Alexey K. Kovalev | 5 | 0 | не установлен | подтверждена | не установлена |
| Mikhail Derkach | 2 | 1 | undated | подтверждена | подтверждена |
| Alexey Maslov | 2 | 1 | historical | подтверждена | не установлена |
| Д. В. Исангулова | 2 | 1 | undated | подтверждена | не установлена |
| Maria S. Ledovskaya | 2 | 1 | undated | подтверждена | подтверждена |

В таблице `historical` означает исторический источник, `undated` — отсутствие установленной даты актуальности контакта. `supported` для личности или аффилиации не превращает адрес в действующий и не доказывает набор студентов.

**Фактически выполненный метод.** Код сначала получил все десять публичных ORCID record по известным frozen ID. Открытых emails и researcher URLs в них нет; полезны имена, занятость и идентификаторы работ. Для анонимного публичного API отдельно сохранены датированные [условия](https://info.orcid.org/public-client-terms-of-service/) и [лимиты ORCID](https://info.orcid.org/ufaqs/what-are-the-api-limits/): этот некоммерческий исследовательский проход использовал anonymous reads без credentials, ≤1 rps, намного ниже опубликованных 12 rps и 25 000 reads/day. HTML robots не подменяет правила отдельного API. Реальный отказ остановил бы доступ; регистрации и обхода квоты не было.

Публичный поиск использовался только для обнаружения точных URL. Доказательства взяты из настоящих сохранённых HTML/API/PDF bodies, с robots, ограничением размера, обычными наблюдаемыми redirects и source-bound offsets/SHA. Получено 25 пригодных источников: 10 API, 11 HTML и 4 PDF. У ВШЭ ссылка на именованный профиль найдена в HTML лаборатории, где совпадает frozen ORCID. У МГУ пробелы вокруг `@` нормализованы из буквального именного блока. В Math-Net два контакта воспроизведены локально точной публичной функцией `decode_email` из наблюдаемого script src; изменённая функция отвергается, произвольный JS не исполняется. Для производных сохраняются неизменный parent HTML, decoder receipt и самостоятельный SHA текста; дополнительные HTTP для этого воспроизведения — 0.

Для первых пяти подготовленных входов лимит кандидатов остался 8/source; для остальных пяти стал 32/source, чтобы не пропустить человека в списке сотрудников. Это зафиксированные версии collector v2/v3, выбранные в одном гибком проходе, не сравнение A/B. Контекст включает непрерывные окна вокруг адреса, публичный ORCID person/employment и совпадающие названия исходных работ. Код сохраняет также чужие и общие адреса как кандидаты; семантическое решение оставлено проверяющему. Получено 45 атомов: 8 приняты как личные контакты, 37 не приняты. У ВШЭ адрес в контактах лаборатории не доказал личную принадлежность. У Ковалёва статья с email указывает другой ORCID, а адреса центра и другого автора не приписаны целевому профилю. Для Маслова старый адрес Texas A&M подтверждён через исходную работу, нынешняя связь с МИФИ — нет.

**Бюджет и проверки модели.** Зарезервировано 57/200 контролируемых попыток, `HTTP_started` у 56, получен HTTP status у 52; DNS/transport failures учитываются в бюджете. Поисковых запросов 23/40, ≤4/person. Внутренние физические HTTP поискового инструмента не раскрыты и не приписаны этому ledger. Автоматических повторов источников или того же профильного задания нет. Весь source/model проход закончен до замороженного 90-минутного deadline; сеть закрыта отдельно, root STOP запрещает новые source/model jobs.

GLM не понадобился: новых GLM 0, Astra 0, native Sol jobs 10 — ровно по одному на каждого человека. Полный прежний semantic-v3, schema и проверка source binding сохранены; сокращённого суррогатного verifier нет. Запрошены `gpt-6.1-sol/high`, необходимые client options проверены, MCP/web отключены в verifier. Receipts не раскрывают фактические server-side model/effort: они сохранены null с `runtime_not_exposed`, поэтому подтверждается конфигурация запроса, а не недоступная серверная аттестация. Expected email/verdicts в input отсутствуют. Другие 17 полей не собирались систематически; unknown готовности означает неустановленность в сохранённых материалах, а не доказанное отсутствие предложения.

Новые профильные задания увеличили дневной счётчик с 7 до 17/30. Native receipts: input 433,904, в том числе cached 12,800; output 25,607, в том числе reasoning 7,177; суммарно input+output 459,511. Cache/reasoning не прибавляются повторно. Сумма model wall time 645.630s, HTTP durations 92.698s; это суммы этапов, не общая длительность работы. Число внутренних физических model requests native CLI и денежная стоимость подписки не раскрыты. Официальный остаток Codex до прохода 13%, после десяти jobs 12%; процент общий для аккаунта, разработку/ревью нельзя отделить из него. Резерв 0 разрешён Борисом; actual refusal, покупки или reset не потребовались.

**Технические доказательства и пределы вывода.** Код сбора зафиксирован до HTTP на f896ebe; перед локальными производными исходники скопированы в SHA snapshots, итоговый код обработки — 437b9ca. Семь meaningful offline checks проверяют literal links, обычный redirect, публичную API policy, общие лимиты/STOP, nonpublic IP/protection refusal, исторические quota floors и воспроизводимость/tamper запрет decoder. `make lint`, `make typecheck`, `make test` PASS: 241 unittest, 388 pytest, 8 skipped, 5 deselected, coverage 94.06%. Четыре PDF contact pages дополнительно просмотрены как изображения техническим агентом; это source QA, не человеческая разметка. Повторно совпали 36/23/184/44 SHA прежних четырёх roots, их результаты и STOP не изменены.

Строгий `make audit AUDIT_ARGS="--no-images --strict"` на итоговом коде по-прежнему FAIL только по известному [#189](https://github.com/borisboriov/search-for-research/issues/189): sharp 0.35.4 GHSA-wq5f-xc86-pv6w и source-map-js 1.2.1 CVE-2026-93749. Проверки не ослаблены. Docs-check с actualmeta, независимое техническое ревью полного нового scope, актуальные CI checkout/parents и readonly handoff фиксируются отдельными receipts и комментариями PR #194. Принятие, merge и production не заявляются.

Рабочий результат эксперимента — доступные источники, восемь проверенных по принадлежности адресов, пять подтверждённых нынешних аффилиаций и явные неизвестности на всех десяти. Следующий полезный шаг — человеческий просмотр десяти private карточек, прежде всего исторических адресов и пяти неподтверждённых аффилиаций; перед использованием в продукте нужно отдельно проверить актуальность контактов. Фоновое продолжение, новые люди и новые задания модели не оставлены.

**Исправление provenance после независимого ревью.** В `plans/07-observed.json` хэш Math-Net parent для неудавшегося перехода к Lebedev относится к строке после нормализации 102 CRLF в LF, а не к сохранённым decoded bytes. Исходный исполненный план оставлен неизменным; отдельный `plans/07-observed.erratum-v2.json` связывает его SHA с исходным byte SHA, normalized-LF SHA и буквальными href/start_tag. Переход остановился на robots failure и не дал контактных доказательств. Source-bound производные, входы модели и результаты не изменены; новых HTTP или профильных jobs — 0.
