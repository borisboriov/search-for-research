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
См. [bounded-v4](../methods/enrichment_cli_bounded_v4.md).

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
исправленную попытку. Подробности: [v2](../methods/enrichment_cli_bounded_v2.md),
[recovery](../methods/enrichment_cli_recovery_v1.md). Автоматических повторов нет.
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

[Пререгистрация](../methods/enrichment_gpt_compact_v1.md): три старых сложных
входа, шесть новых Sol/high jobs, одна и та же полная source JSON и все identity
anchors/цитаты. Baseline — полная инструкция со schema в prompt+output-schema;
compact — [краткая инструкция](../methods/enrichment_verifier_compact_v1.md)
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
Метод дополнительного этапа: [fresh compact control](../methods/enrichment_fresh_compact_control_v1.md).

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

После завершения всех измерений исправлен [host deadline](../methods/enrichment_cli_host_deadline_v1.md):
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
[правила](../methods/enrichment_cli_early_read_v6.md),
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

## Перенос автономного сбора на GLM: методика перед запуском

Новое поручение в PR #194 закрепляет повторяемый runner и отдельно проверяет
live discovery GLM-5.3-Flash/high на неизменном frozen10. Полная постановка и
ограничения: [runner](../methods/enrichment_glm_runner.md). Baseline остаётся
запечатанным; 459511 токенов относятся только к его десяти verifier jobs, а
расходы главной сессии Sol по выбору поиска/источников неизвестны. Новый запуск
не получает прежние контакты, deep URL или verdicts. Sol 6.1/high повторно
оценивает обе стороны с полной semantic-v3; результаты добавляются после
фактического запуска. Измерения стоимости разных ролей разделены.


### GLM runner: частичный остановленный live-проход

**Вывод.** Повторяемый CLI и безопасные source tools реализованы, но перенос
рабочего сбора на GLM и отсутствие ухудшения **не подтверждены**. Единственный
live-проход frozen `f5454ea1950cdf3ecc14a2c9247eb379ce7a4eaa` остановлен по
High замечанию независимого ревью. Новых профильных/source jobs после STOP нет;
исправленную версию проверяли offline, а не повторным подбором на этих людях.
Постановка до первого вызова — [PR comment6101794842](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6101794842),
исходный fail — отдельный комментарий с точным диапазоном. Методика и команда —
[GLM runner](../methods/enrichment_glm_runner.md).

**Фактическая цепочка.** Zero-inference Pi live/replay preflight и offline
source binding проверки прошли. Baseline seal865 файлов сохранён; исходный
pypdf6.10.0 воспроизвёл четыре allowlisted PDF и все10 source-bound входов,
а live dependency обновлён до6.19.0 без audit исключений. GLM не получал прежние
emails, deep URL, нормализованные факты или verdicts. Он сам выполнил7 native
Z.ai search и1 ordinary DuckDuckGo HTML query; поиск возвращал преимущественно
корни. Код сохранил5 source records (2 ORCID,3 HTML) и9 controlled HTTP
reservations/started requests. Поисковые сниппеты не использовались как факты.

| Автор в frozen порядке | Baseline: принятые контакты прежним Sol | Новый GLM status | Новая независимая пара |
|---|---:|---|---|
| Salman Ahmadi‐Asl | 1 | Завершён, source binder отклонил цитату | Не проверена |
| Evgeny Styrin | 0 | Прерван после review STOP | Не проверена |
| О. В. Тушавина | 1 | Не запускался | Не проверена |
| Alena Nastulyavichus | 1 | Не запускался | Не проверена |
| И. В. Морозов | 1 | Не запускался | Не проверена |
| Alexey K. Kovalev | 0 | Не запускался | Не проверена |
| Mikhail Derkach | 1 | Не запускался | Не проверена |
| Alexey Maslov | 1 | Не запускался | Не проверена |
| Д. В. Исангулова | 1 | Не запускался | Не проверена |
| Maria S. Ledovskaya | 1 | Не запускался | Не проверена |

Прежние оценки в таблице — история baseline, не gold и не повторная проверка.
Новых source-bound GLM inputs0, новых Sol пар0. Поэтому новые identity,
контакты, current_affiliation и readiness неизвестны; ноль проверенных пар
не означает нулевое качество GLM или доказанную регрессию. Human0.

**Остановка и исправления.** Независимый sfr-reviewer установил пять блокеров
f5454ea: swallowed hook exception допускает fail-open cap/model/STOP; MCP
semantic refusal при HTTP200 не ставит latch; nested JSON snippet может
зарегистрировать URL; partial receipts недосчитываются; empty unknown pairs
могут получить vacuous nonregression. Запуск остановлен в20:26:10UTC после
11+6 model requests, до превышения12/person; фактического quota refusal и
превышения cap не наблюдали. Первый job имел корректно отклонённую недословную
quote; второй завершён внешним SIGINT. Сохранены первичные metrics, receipt,
request payloads и frozen snapshots. Recovery receipt восстановлен из SHA
зафиксированных events, started и STOP; reconciled metrics дописаны отдельными
файлами. Primary metrics показывали только первый receipt и11requests;
пользоваться следует reconciled projection, не первичным недосчётом.

Исправленная версия ставит terminal STOP на callback failures, отдельно
ограничивает физический fetch, прекращает MCP quota/access refusal, разбирает
только actual search rows без snippet recursion, сохраняет interrupt receipt,
разделяет неизвестные полные расходы и observed sums и требует quality
eligibility. Девять meaningful Python tests и два JS tests проверяют эти
границы без сети/model jobs, включая имитацию Pi swallowing и запрет13-го
физического fetch. Исправленный runner ещё не прошёл полный live comparison.

**Расходы и знаменатели.** [Reconciled metrics](enrichment_glm_runner_20261010.metrics.json)
и [статусы](enrichment_glm_runner_20261010.status.json) — точные копии
детерминированных публичных проекций private root
`/Users/boris/Experiments/search-for-research/enrichment-glm-runner-live10-20261010`.
Начаты2 GLM jobs, завершён1 (без допустимого извлечения), второй прерван.
Сохранены17 model configs и17 native model HTTP200 observations; контролируемых
HTTP9, логических search8. Отдельно записаны native MCP protocol/search HTTP,
включая инициализацию; они не приравниваются к числу поисковых запросов.

Наблюдённые Pi usage: uncached input72897, cacheRead88320, cacheWrite0,
output6536, всего167753. Cache уже исключён из Pi input; reasoning отдельно
не раскрыт и входит в output. Это **нижний предел частичного прохода**, полный
job usage неизвестен (`null`). Сумма observed wall213.975s включает прекращение
второго процесса, не является точным inference time. Sol jobs0, Astra0,
день17→19/30. Остаток Codex до запуска9%, ordinaryUsageAllowedtrue, резерв0
разрешён; reset/покупок не было. Доля квоты общая для аккаунта: разработку и
ревью нельзя выделить из неё. Baseline verifier459511 tokens/645.630s на10
людей, его главная сессия неизвестна; сопоставимых новых Sol пар нет.
Полную экономию цикла, стоимость в долларах и масштабирование не заявляем.

**Передача.** Source/model процессы остановлены; первоначальный baseline и
старые seals повторно сверяются. Независимая повторная проверка исправлений,
итоговый head, CI и readonly handoff фиксируются в PR. #189 вне scope:
локальный strict audit остаётся FAIL по прежним sharp/source-map-js, при
исправленном pypdf. Merge/deploy/продуктовая приёмка не заявляются. Для вывода
«качество не хуже» нужен отдельный ограниченный прогон исправленной цепочки
и полная независимая проверка; этот раунд не подменяет её partial-цифрами.


### GLM remaining8: новый freeze и STOP на кодировке источника

**Вывод.** Разрешённое продолжение на ещё не пройденных этим методом восьми
профилях осталось техническим partial. Новых independently verified пар —
0; неухудшение качества и преимущество полного цикла по расходам
не установлены. Это devset с известным агентским baseline, human0;
восемь не подменяют единый чистый новый10-run. Исходный baseline для remaining8
имел 7 принятых агентом контактов, supported identity8 и current affiliation3;
эти старые оценки не являются human gold и не были переданы GLM.

**Постановка и версия.** [Продолжение в PR](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6102242505),
[pre-live независимое pass](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6102293012).
Frozen `4e85631cfd79e84398a9ffacdc7bbfaf23509d17`; новый root
`/Users/boris/Experiments/search-for-research/enrichment-glm-remaining8-20261011`.
Старые STOP и метрики не менялись. Перед запуском проверены refs/чистый own
checkout/единственный исполнитель, seals605 файлов предшественника и865 baseline,
252 unittest,388pytest,11offlinePython и2JS. Минимальный native Pi preflight
завершился без inference/source/search:0/0/0. Narrow schedule/budget patch
сохранил collector instruction/schema (AST SHA proof), source binder и полную
semantic-v3. Исходное Medium замечание first-pair context skip исправлено
**до** freeze; продолжение требует фактически проверенной первой пары.

Новый freeze: `2026-10-10T21:20:16.107438+00:00`, finite deadline
`2026-10-10T23:50:16.107438+00:00` (150минут), фиксированные группы1+3+4,
max8GLM+3Sol. Общий счётчик цикла начат с19 и не сброшен при смене даты;
первые два прежних ID A5070748575/A5047877230 исключены до reservation.
Astra0, reserveCodex0 разрешён, покупок/reset/API billing нет. На старте
официальный остаток6% account-wide, ordinaryUsageAllowed=true. Чтение логов
продуктовым координатором не является его независимой локальной перепроверкой файлов.

| Scheduled ID | Фактический исход нового прохода | Новая Sol-пара |
|---|---|---|
| A5006480668 | Завершён, цитата не найдена в saved body; весь packet отклонён | Не проверена |
| A5011172734 | Прерван необработанным LookupError charset windows-874 | Не проверена |
| A5069670094 | Не запускался | Не проверена |
| A5054791318 | Не запускался | Не проверена |
| A5065694561 | Не запускался | Не проверена |
| A5054586424 | Не запускался | Не проверена |
| A5089458364 | Не запускался | Не проверена |
| A5042154547 | Не запускался | Не проверена |

**STOP и строгая граница.** Первый job прошёл transport/schema, но дословный
binder отверг цитату; готового source-bound input нет. Это отдельная ошибка
профиля, поэтому второй job начался без повтора первого и без пустой Sol-проверки.
На втором обычный публичный HTML объявил charset `windows-874`; Python
`raw.decode` выбросил `LookupError`, не преобразованный loader в локальный
отказ источника. Common local цепочка прервана, native Pi завершён, outer finally
сохранил STOP `2026-10-10T21:26:26.049670+00:00`; runner exit1.
Исходный `metrics.json` не переписан. Recovery receipt имеет SHA первичных
started/events/STOP, отдельные `metrics-reconciled.json`/public/status фиксируют
прерванный job. Остальные шесть не запускались. Provider quota refusal не
наблюдался; общий profile count `19→21/30`.
После STOP новые источники/модели не вызывались.

**Автономность и расходы.** GLM сам выбрал 6 native Z.ai search и
2 ordinary DuckDuckGo HTML query. Snippets — только discovery;
ручной подбор URL главной Sol-сессией0, baseline emails/deep URLs/verdicts
в collector0. Код сохранил 7 источников
(ORCID2,HTML5,PDF0),
14 HTTP reservations/14 started, 8 логических поисков.
New GLM jobs2: один completed, второй interrupted; Sol jobs0, пары0.
19 model request configs и 19 native model HTTP observations.

| Наблюдаемое GLM usage | Токены |
|---|---:|
| Uncached input | 87355 |
| cacheRead отдельно | 118784 |
| cacheWrite | 0 |
| Output, включая невыделенный reasoning | 15896 |
| Наблюдаемая сумма | 222035 |

Суммы — наблюдённый нижний предел прерванного прохода, полнота job accounting
false; полные точные tokens/wall `null`. Reasoning отдельно не раскрыт и не
прибавляется к output; backend/USD неизвестны. Наблюдаемая wall-сумма
366.476759сек включает bounded termination overhead для recovery,
а не точное время полного цикла. Sol input/cached/uncached/output расходов новых
проверок0: jobs не было. Контакты сохранены/потеряны, ложные добавления,
identity/affiliation/date/readiness **не переоценены**, это не качество0/8.
Старые459511 токенов относятся только к10 baseline verifier jobs; coordinator,
поиск и оркестрация baseline неизвестны. Поэтому отношение этих сумм не является
экономией, API-цена/масштаб1000–10000 не заявлены.

**Исправление после STOP и передача.** Unsupported codec теперь преобразуется
в ValueError отдельного source call: raw bytes сохранены, guessed decoding нет,
иной публичный источник может быть прочитан. Регрессия проверяется offline
mock HTTP: unknown charset оставляет body/ledger без accepted source, следующая
обычная UTF-8 страница проходит, исходный URL не повторяется. Эта корректировка
не запускалась live на тех же людях; frozen4e и STOP сохранены. Финальное
независимое ревью/CI/handoff относятся к окончательному head PR и опубликованы
там отдельно. Строгий аудит продолжает раскрывать #189; merge/deploy нет.

**Воспроизводимость.** [Публичные числовые метрики](enrichment_glm_remaining8_20261011.metrics.json)
и [состояние расписания](enrichment_glm_remaining8_20261011.status.json) — точные
bytes private projections, а не вручную пересчитанные значения. Primary raw,
quotes/source bodies/receipts, recovery provenance, STOP, code snapshots и
проверки остаются в новом private root; в git нет emails/сырых цитат. Старые
baseline/partial/seals не перезаписывались. Итоговый SHA-index и подтверждение
прекращения процессов сохраняются перед передачей.


### GLM remaining6: завершённый проход, непригодные пакеты и потеря исторического контакта

**Вывод.** Единственный frozen40e560d прошёл все6 оставшихся профилей без
нового системного блокера: source-bound1/6, independently paired1/6.
Четыре пакета отвергнуты за недословные цитаты, один — за URL без сохранённого
тела. В единственной паре Alexey Maslov сохранена supported identity, но GLM
не сохранил один подтверждённый повторной агентской проверкой исторический
личный контакт2007. Это **не потеря подтверждённого нынешнего адреса**:
applicability baseline historical. Данная ограниченная версия автономного
GLM-сборщика ненадёжна и не выполняет критерий сохранения полезных фактов.
Качество остальных5 семантически не сравнено; общий вывод «GLM слабее Sol»
из этого devset не следует. Human/gold0, baseline8contacts не человеческий gold.

Постановка — [remaining6 scope](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6102719319).
Frozen head `40e560deac8049828cab3c347e307bf352bea411`, base/merge base
`accc508cd398b5e57105fe1c45f906f89330d636`. Pre-live расширен только план:
две chain seals, excluded4, счёт21→≤30, groups2+2+2; по независимому замечанию
добавлен global STOP при systemic host_error, включая пустой текст ошибки.
[Fail5e](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6102752412)
закрыт [Pass40e](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6102776693)
до source/model calls. Instruction/schema AST, binder, decoderb810 и полная
semantic-v3 неизменны. Ни код, ни план, ни prompt во время прохода не менялись.

Root `enrichment-glm-remaining6-20261011`, freeze 2026-10-10T22:18:46.073540+00:00;
новый finite deadline 2026-10-11T00:48:46.073540+00:00 (150минут),
STOP 2026-10-10T22:41:47.327516+00:00; full root wall 1381.254s.
Предыдущие2+2 attempts, их STOP/raw/metrics/seals и deadlines сохранены;
четыре ID не повторялись. Новые6 и старые2+2 — разные версии/проходы,
не чистый единый10-run. Старый агентский baseline на scheduled6 имел
5contact profiles, supported identity6,
current affiliation3; это не gold.

| Профиль | GLM requests | Пригодный packet | Парная проверка | Итог |
|---|---:|---|---|---|
| И. В. Морозов (A5069670094) | 11 | нет | нет | Недословная цитата |
| Alexey K. Kovalev (A5054791318) | 11 | нет | нет | Недословная цитата |
| Mikhail Derkach (A5065694561) | 7 | нет | нет | URL без сохранённого тела |
| Alexey Maslov (A5054586424) | 11 | да | да | Потерян исторический контакт2007; identity сохранена |
| Д. В. Исангулова (A5089458364) | 11 | нет | нет | Недословная цитата |
| Maria S. Ledovskaya (A5042154547) | 11 | нет | нет | Недословная цитата |

**Семантика только одной пары.** Повторно проверенный baseline1 исторический
контакт, GLM0: lost contact1. Supported identity1→1; current affiliation
insufficient→insufficient, readiness unknown→unknown. Identity/affiliation
loss0, непринятых GLM atoms0 и изменений даты/применимости общих контактов0
**только в этой паре**; у остальных5 эти показатели unknown/null.
`original_baseline_changed_on_recheck=true` сохранён в первичных метриках:
полное структурное сравнение видит дедупликацию одинакового source URL3→1
при lossless compaction. После нормализации списка источников факты,
значения, дата2007 и historical applicability совпадают; это не смысловая
смена baseline-оценки. Отдельный private annotation фиксирует эту оговорку.

**Источники и ошибки извлечения.** Ошибки source tool возвращались локально,
счётчик ошибок именно `sfr_source` — 27, категории {"other_local_source_error": 6, "cached_unsuccessful_source": 3, "unregistered_URL": 8, "robots_refusal": 10}.
Это не число уникальных недоступных источников:14 первичных source refusals
(9robots,4access,1invalid UTF-8),4 cached failures без нового HTTP retry,
8 незарегистрированных URL в выборе GLM и1 попытка превысить profile search
limit. Последние9 относятся к использованию инструментов моделью, а не
недоступности сайта. Подробная атрибуция сохранена отдельным private JSON;
первичная более грубая группировка не переписана. Отдельно native_search
отклонил ещё6 IPC запросов по Frozen search cap без новых search reservations:
это дополнительно к1 limit отказу public_search внутри sfr_source. Всего
наблюдаемых denied IPC tool requests33; дополнительные6 не увеличивают
23 logical queries, не являются provider quota refusal и не превышают cap.
Controlled HTTP45reserved/45started,
20accepted source records: {"direct_http": 14, "structured_orcid": 6}.
Search23 logical query reservations (не23 успешных поиска): {"public_DuckDuckGo_HTML": 4, "native_Zai_search": 19}; source tool calls70.
Native Pi/Z.ai сам выбирал реальные search rows/наблюдённые href и атомы;
main Sol source choices0, baselineemails/deepURLs/verdicts не передавались.
Source-binding failures4+1 отделены от source availability: они означают
непригодные доказательства в output, а не отсутствие контактов или пять
семантически измеренных потерь. Непригодные packets не расходовали Sol.
Группы00/02 skipped без modeljob; группа01 проверила только пригодный Maslov.
Полные индивидуальные inputs/рубрика не сокращались ради context cap.

**Расходы.** New GLM6 reserved/started/completed/receipts;62 physical model
requests и62 headers observations200. Max12/model requests,24/source calls,
4/search на человека не превышены. Sol1 groupjob,2 individual tasks,1paired;
shared cycle21→28/30, Astra0, retry0; providerquota отказа и общего runtime
сбоя не наблюдалось. GLM reported usage complete: input uncached264361,
cacheRead429952, cacheWrite0, output55727, total750040; reasoning отдельно
не раскрыт и входит в output. Collector wall1309.131s включает source I/O.
Sol reported input27240 (cached0), output3602 (reasoning755 уже внутри),
total30842, wall67.071s. Новый измеренный model total780882, сумма wall1376.202s;
эти суммы не включают неизвестную стоимость search/backend/разработки.
Native Sol requested6.1/high, tools0; actual server model/effort/runtime
не раскрыты receipt. Клиент сообщил CodeMode host disabled, но вернул
полный schema/SHA-valid результат; code tools этому verifier не требовались.

Для того же одного профиля прежний verifier: input33821, output2440,
total36261, wall56.220s. Нынешний verifier оценивает две стороны, прежний одну;
малое различие этих затрат не доказывает экономию сборщика. Baseline459511
tokens/645.630s — только10 verifier, collector/coordinator/search неизвестны.
Прежний первый GLM2:17requests/минимум167753tokens/day17→19;
следующий GLM2:19requests/минимум222035tokens/day19→21;
нынешний GLM6:62requests/750040tokens/Sol1/day21→28. Старые partial totals
не превращены в точные; даты не сбрасывают30-job cap. Покупок/reset/paid API
и новых аккаунтов не было; official quota перед freeze4%, reserve0 разрешён.
Accountwide delta не приписывается эксперименту. Экономия полного цикла,
APIUSD и масштабирование1000/10000 не установлены.

**Проверки и передача.** До freeze lint/typecheck/255unittest388pytestPASS,
docs-check с actual meta9002PASS, независимый pre-livePASS. Audit strict
раскрывает только deps-node/fs-trivy из #189; текущие frozen40e checks/webPASS,
auditFAIL, реальный CI checkout/parents сохранены private. Финальное ревью
docs/results и CI финального head закрепляются в PR отдельно; handoff до
зелёного audit не подтверждён. DoD bounded6 выполнен по scope/лимитам/
immutable evidence/пригодной полной паре/STOP; критерий nonregression и
надёжного контакта не выполнен. Merge/deploy/продуктовая приёмка не заявлены.

Источник чисел — immutable private `metrics.json`, `execution-status.json`,
`execution-evidence-summary.json`, receipts и source/model ledgers. Public
JSON [metrics](enrichment_glm_remaining6_20261011.metrics.json) и
[status](enrichment_glm_remaining6_20261011.status.json) совпадают байт-в-байт
с private projections. Primary metrics не переписаны, private контакты и
quotes вне git. Итоговый transfer SHA-index и прекращение процессов/записи
будут зафиксированы в комментарии PR. Новых экспериментов после этого STOP
не назначено; #189 не исправлялась попутно.

## OFFLINE fragment-ID paired3, 11.10.2026: partial/STOP

**Итог: данных недостаточно.** Новый этап остановлен из-за технического
расхождения порядка модельного входа. Есть одна незавершённая GLM попытка,
Sol0, completed0, пригодных пар0. Identity/contact/date/affiliation/readiness,
пропуски и false additions не оценены; качество GLM по этому проходу неизвестно.
Это не доказательство регрессии GLM и не повтор прежнего отрицательного live
эксперимента. Источник чисел — generated
[public metrics](../methods/enrichment_fragment_offline3_20261011_public_metrics.json),
побайтовая копия нового private `public-metrics.json`.

### Scope, заранее выбранные случаи и общий корпус

[Постановка](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6105694857)
разрешила отдельный конечный OFFLINE этап после завершённого cycle28/30:
максимум3GLM5.3Flash/high через существующий Pi/Zai +3Sol6.1/high,
deadline2026-10-11T08:06:54Z, ≤600s на весь job, без повторов/Astra.
Search/source/live/new10 запрещены. Новый счётчик не обнуляет старый;
разработка и независимое ревью отделены от профильных jobs.

До inference зафиксирован порядок: ИсангуловаA5089458364 — прежняя недословная
цитата; MaslovA5054586424 — пропущенный historical контакт2007;
KovalevA5054791318 — сложная атрибуция чужих/общих адресов.
Выбор по прежним ошибкам, без результатов нового метода; прежние ответы,
вердикты и готовые атрибуции не входят в prompt. Полная semantic-v3 неизменна.
Все saved source/rendered records flexible10+remaining6 проверены по исходным
bytes/деривации и объединены с дедупликацией URL/bodySHA/textSHA.

| Случай | Records → sources | Fragments | Literal email candidates | Prompt bytes |
|---|---:|---:|---:|---:|
| Исангулова | 6 → 4 | 54 | 3 | 141908 |
| Maslov | 5 → 4 | 37 | 5 | 103157 |
| Kovalev | 11 → 10 | 188 | 26 | 478797 |

Math-Net rendered representation Исангуловой с двумя дополнительными email
включена из уже сохранённых parent/decoder bytes, без загрузок. У Maslov нужный
historical контакт отсутствует в новых acquired remaining6 телах: полный
baseline source с этим фактом явно добавлен обеим моделям. Это проверка анализа
общего корпуса, а не эффективности retrieval. Corpus целиком разбит обычным
кодом на1800chars/step1500, с CRLF и буквальными email spans; модель должна
выбрать ID и дать полную семантическую атрибуцию. Свою атрибуцию одного job
не выдаём за независимую вторую проверку себя. Human/gold0, согласие Sol неgold.

### Freeze, обнаруженный runtime дефект и terminal STOP

Новый root:
`/Users/boris/Experiments/search-for-research/enrichment-fragment-offline3-20261011`.
Frozen head `6a0f5e8f2cee23a80fc9a34c2f7d6081494036b0`, manifestSHA
`adf1a5d7c6af2968ec47cf1476308339b640c16d17bf1bf164807186eacd2ba1`.
Freeze и нулевой job counter сохранены
[до вызова](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6105882188).
[Pre-inference review](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6105878639)
закрыл две Medium находки: общий600s deadline, включающий isolation probe,
и пропущенные rendered sources. Этот PASS не подтверждает фактический runtime.

В первой GLM попытке `encoded(sort_keys=True)` пересортировал вложенные ключи
task/corpus/fragments/schema перед `JSON.stringify`. JSON-данные равны,
инструкция SHA совпадает, но порядок и prompt bytes отличаются. Frozen SHA:
`771ab46b877d8423a9db96af4ca10dcd4e20a614c79098013369dd6dde3c9d83`;
actual Pi SHA:
`995824fe85c8517c13e7539836bdf18f3ff25031d9e9a234bc94e48147a24356`.
Это нарушает требование одинакового порядка двух моделей. Автор остановил
только собственный parent process; его finally завершил child и сохранил
`execution-result.json`/`stopped.json`: operator_interrupt, donefalse, exit-9.
[Независимое runtime ревью](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6105925989)
подтвердило дефект и счётчики, frozen FAIL/blocking1.

Фактически: GLMreservation1, model-request artifact1, physical HTTP2001;
Sol0, normalized0, result0, receipt0, terminal assistant events0. Stage1/6,
cumulative28→29/34; прежний cycle28/30 неизменен. Оставшиеся пять jobs и повтор
запрещены terminal STOP. Source/search0, tool inventory пуст, Astra0. Частичный
поток не считается готовым ответом или пригодным source-bound извлечением.

### Расходы и границы выводов

Прерванная попытка заняла207.08461570739746s, 05:35:38.868138–05:39:05.952701UTC.
Это wall до прерывания, не wall успешного job. Нет terminal usage: промежуточные
SDK нули при stopReason=pending — placeholders. Полные input/output/cacheRead/
cacheWrite/total/reasoning tokens неизвестны; не считаем их нулём. Денежный
расход и subscription debit неизвестны. Requested/effective SDK config —
zai/glm-5.3-flash/high; фактический backend model/effort не раскрыт.
Account-wide процент квоты не является debit этого эксперимента. Reset-credit,
покупки и paid API не использованы. Токены/деньги разработки, reviewer и двух
read-only helpers не измерены и не смешиваются с одной профильной попыткой.
Экономия полного коллектора не установлена; поиск был выключен.

### Offline исправление, проверки и DoD

После STOP исправлен только код: вложенный порядок request сохраняется для
fragment метода, ожидаемый общий SHA передаётся из manifest; Python проверяет
его до запуска, JS — до model request, driver — по actual receipt. Прежние
методы и исходные frozen bytes сохранены. Regression test использует несортированные
вложенные fragments/schema keys; offline proof actual `run_pi` serializer с
mocked process и реальным JS helper воспроизвёл все три frozen SHA/bytes.
Новых model/source calls, нового root/freeze или переоценки raw нет.

Lint/typecheck PASS,263 unittest/388 pytest PASS; JS20PASS, docs-check проверен
отдельно. Strict audit обязателен и остаётся FAIL по deps-node/fs-trivy #189;
две HIGH уязвимости sharp/source-map-js, повторно найденные двумя сканерами.
В логе четыре CVE/GHSA идентификатора тех же находок из #189, а не четыре
разных уязвимости; исключения/критерии не ослаблялись. Его history mount
просканировал0commits; отдельный read-only history scan frozen6a0 проверил
501commit/0leaks. CI frozen6a0 checks/webPASS,auditFAIL, actual merge checkout
и родители совпадают с текущими base/head. Финальное ревью исправленного кода,
документов и CI нового head закрепляются отдельным последним маркером PR.

DoD фиксации scope/корпуса/лимитов/STOP/сохранности выполнен; DoD paired3 и
сравнения качества не выполнен. Ни надёжность метода, ни преимущества GLM/Sol
не заявляются. Следующий конкретный шаг: рассмотреть новый отдельно разрешённый
bounded запуск только после offline проверки фактической сериализации до calls;
этот отчёт его не назначает. Полный issue193 не закрывается, merge/deploy и
продуктовая приёмка не заявлены. Изменения паспорта не требуются: принятые
продуктовые цифры не меняются. Старые STOP/raw/метрики/human сохраняются.

## 2026-10-11: отдельно разрешённый повтор OFFLINE paired3 на актуальном main

[Прямое поручение](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6106101964)
разрешило обычным merge обновить собственную ветку и повторить те же три случая после
исправления сериализации. Main `99bf7c6cbc220ebec1111a496ea237183cd544f9`
содержит merged PR196/fix189; merge без конфликтов выполнен коммитом `25599ec`.
Это новый конечный этап, отдельно от прежнего завершённого cycle28/30 и
terminal partial1/6. Старые STOP/raw/метрики/seal не переоценивались и не менялись.

Новый root:
`/Users/boris/Experiments/search-for-research/enrichment-fragment-repeat3-20261011`.
Frozen head `826d25d168971e824fda4a60635b3960424f7fd2`, manifestSHA
`e2c4354188c1f2d8d28c4a22e783eeb8d295ba16db5d1a514df87264fda5a46d`.
[Fresh pre-inference review](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6106226306)
прочитал полный текущий диапазон 122 файлов и перепроверил исправление Medium:
первичный SDK assistant error при HTTP200 теперь прекращает этап, а не разрешает
следующие jobs. [Freeze/proof до calls](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6106233854)
фиксирует нулевые jobs и source calls.

Corpus/task/instruction каждого случая побайтно равны предыдущему partial.
Actual Python run_pi serializer→JS helper повторён на новом root через mocked
Popen до сети. Общие SHA/UTF-8 sizes: Исангулова `771ab46b…`/141908,
Маслов `6e135865…`/103157, Ковалёв `22e79ac2…`/478797.
В реальном Pi пути сохранён pre-send SHA guard; фактические runtime proof
сопоставляются с manifest. Источники и semantic-v3 полные, без old verdicts,
новых источников/людей, live/search/Astra. Source IDs и буквальные spans фиксирует
код; семантическая классификация остаётся суждением модели.

Лимиты: один run, максимум6 новых profilejobs (3 GLM5.3Flash/high и
3 Sol6.1/high), cumulative29→35, retry0; 600s/job включая isolation probe.
Весь этап начат06:07:02UTC, конечный deadline09:07:02UTC. При локальном output
failure допускаются другие независимые jobs; общий input/provenance/refusal/
deadline прекращает этап. Cron PAUSED; нового monitor или product-message нет.

### Результаты и сравнение трёх пар

Этап завершён terminal STOP в `2026-10-11T06:51:53.110152+00:00`, раньше deadline.
Все шесть runtime jobs вернули raw и terminal usage. Валидатор принял четыре
результата: GLM1/3, Sol3/3; полностью нормализована одна пара из трёх.
`stage_jobs_completed=4` в execution означает принятые normalized outputs,
а не число завершённых runtime jobs. Два failure — локальная валидация GLM;
их raw/receipt сохранены без ремонта или повторов. Cumulative reservations35
(старые28+1, новые6), source/search/Astra profilejobs0, human gold0.

[Публичная проекция метрик](../../../docs/metrics/enrichment_fragment_repeat3_20261011.json)
сгенерирована из terminal receipts, normalized результатов и отдельного offline
raw-аудита. Полные цитаты, буквальные контакты, source IDs и SHA находятся в
private root: `analysis-detailed.json`, `raw-audit.json`, `corpora/`, `runs/`,
`failures/`; адреса в git не публикуются. Raw-аудит всех выбранных spans прошёл
для27атомов (GLM15, Sol12); он не исправляет schema и не превращает rejected
output в accepted result. Буквальная привязка не доказывает смысловую атрибуцию.

| Случай | GLM raw → pipeline | Sol → pipeline | Отдельный прежний agent baseline |
|---|---|---|---|
| Исангулова A5089458364 | Identity supported; личный контакт undated выбран. Affiliation supported2019 и activity active2024 чрезмерно уверены для октября2026. Readiness unknown. Rejected: date guard. | Accepted4atoms; личный контакт1undated. Identity supported, affiliation insufficient, activity unknown, readiness unknown. | Личный контакт1undated; identity supported, affiliation insufficient, activity unknown, readiness unknown. Контакт выбран обеими новыми моделями; GLM pipeline его не принял из-за failure. |
| Маслов A5054586424 | Identity supported; личный контакт2007 выбран, affiliation insufficient. Activity объяснена как unknown, но обязательный status отсутствует; readiness unknown. Rejected: schema. | Accepted2atoms; личный контакт1historical2007. Identity supported, affiliation insufficient, activity unknown, readiness unknown. | Личный контакт1historical2007; те же осторожные profile verdicts. Контакт выбран обеими новыми моделями; GLM pipeline его не принял из-за failure. |
| Ковалёв A5054791318 | Accepted7atoms; автоматически атрибутирован один historical contact candidate2020, несмотря на два ORCID. Identity supported, activity active2026; affiliation conflicting не доказано как взаимоисключение. Readiness unknown. | Accepted6atoms; тот же контакт выбран, identity/object conflicting, personal coverage0. Identity основного профиля supported, affiliation insufficient, activity active2026, readiness unknown. | Personal contact0 из-за конфликта ORCID; identity supported, affiliation insufficient, activity active2026, readiness unknown. Общий полный корпус даёт новую DOI-связь, отсутствовавшую в прежних selected evidence. |

Прежний baseline — агентская оценка меньшего предварительно отобранного входа,
а не gold и не равный новому полному корпусу input. Поэтому сравнение с ним
показывает конкретные сохранённые/новые свидетельства, а не измеренную accuracy
или non-regression одинаковых входов. Две baseline personal selections сохранены
в raw обеих моделей; Sol сохраняет их и в normalized. GLM теряет оба целых
результата на pipeline, а не пропускает контакты при выборе. Для Ковалёва
baseline personal0: новой кандидатуре нельзя присвоить false-positive или
true-positive без независимого разрешения идентичности. Подтверждённых чужих
личных адресов среди выбранных и принятых personal outputs не найдено;
полнота по всем фактам корпуса и precision/recall без human gold не установлены.

**Исангулова.** Личный span
`A5089458364-S0f64f84fd1e096322f28-M570-587` находится в
`A5089458364-S0f64f84fd1e096322f28-F0-1800` под буквальными
«Персоналии: Исангулова Дарья Васильевна» и «E-mail:».
GLM отдельно отвергает как личные адреса поддержку Pure
`A5089458364-S8943b8c36415f42d8c44-M1238-1249` («Техническая поддержка»)
и footer `A5089458364-S0f64f84fd1e096322f28-M7673-7698` («Обратная связь»).
Фактический failure касается affiliation date2019-12-11: cited employment
fragment `A5089458364-Sb86fd6644a761cd763de-F1500-3300` содержит типизированный
`last-modified-date.value=1576026926116`, что детерминированно соответствует
UTC2019-12-11T01:15:26.116Z. Guard требует буквального календарного года2019
в cited text и отвергает эту конверсию; это не свидетельство выдуманной даты.
[Issue197](https://github.com/borisboriov/search-for-research/issues/197)
фиксирует Medium false rejection, OPEN/Todo. Само обновление записи в2019
и отсутствие end date не доказывают нынешнюю аффилиацию; публикации2024
не устанавливают activity в октябре2026. Эти semantic ограничения остаются
отдельно от дефекта guard.

**Маслов.** Span `A5054586424-S15073c828aa4b0e9c3bb-M504-527`, fragment
`A5054586424-S15073c828aa4b0e9c3bb-F0-1800`: «Alexey Maslov»,
«Texas A&M University Libraries», «Senior Software  Application Developer».
DOI `10.1045/november2007-phillips` связывает saved D-Lib статью2007
с self-claimed ORCID work; остальные четыре author addresses не принимаются
за личные контакты Маслова. Точная причина rejection — отсутствующее поле
`profile_assessments.activity.status`, текст объяснения его не заменяет.
Отдельный offline аудит видит ещё calendar dates из metadata:
1383129272675→UTC2013-10-30 и1560359761393→UTC2019-06-12.
Это реальные timestamp conversions, но GLM пометил их date_basis=content;
выбранный `person_status/current` описывает состояние ORCID record, а не
жизнь/занятость человека. Эти ошибки не выдаются за фактическую первую причину
failure: schema остановила нормализацию раньше. TAMU2007 и пустой employment
не подтверждают и не опровергают нынешнюю аффилиацию МИФИ.

**Ковалёв.** Span `A5054791318-Sf416ce05a426acbba486-M626-646`, fragment
`A5054791318-Sf416ce05a426acbba486-F0-1800`: «КОВАЛЁВ А.К.» и
ORCID0000-0001-7309-7382 отличаются от profile ORCID0000-0003-2180-0990.
Обе новые модели явно видят дополнительную DOI-связь
`A5054791318-Sb31852ab07eeb1e4cc0b-F106500-108300`:
`10.17759/exppsy.2020130111`, `source-orcid=0000-0003-2180-0990`,
`source-name=Alexey Kovalev`, `source-client-id=null`. Это self-claimed work
владельца профиля: свидетельство сильнее прежнего baseline, но ещё не разрешает
расхождение двух ORCID. GLM принимает историческую кандидатуру, Sol учитывает
тот же bridge и сохраняет conflicting; Sol не пропустил DOI. Нынешняя
доступность контакта и личность его владельца человеком не подтверждены.

Общий контакт центра `A5054791318-Sc862ffc709370d0ff265-M6700-6716`, fragment
`A5054791318-Sc862ffc709370d0ff265-F6000-6730` («Contact us:»), обе модели
не принимают как personal или student coordinator coverage. Проектные
recruitment/skills сведения `A5054791318-Sc862ffc709370d0ff265-F3000-4800`
не доказывают индивидуальную готовность руководить или нынешний набор.
GLM topic `A5054791318-Scd4806a109e095aad11a-F0-1800-text` с записью HELP2027
помечен current при saved checked_at2026-10-10: будущая запись списка
не доказывает уже состоявшуюся публикацию или нынешнюю активность.
GLM activity explanation тоже использует2027; достаточные отдельные основания
activity — версия статьи2026-03-04 и ORCID publication2026-05-22.
Affiliation conflicting у GLM чрезмерно категорично: MIRIAI/AXXX и
неподтверждённое МФТИ могут сосуществовать; raw сам допускает совместительство.
Sol оставляет affiliation insufficient. Эти ограничения сохраняются в raw
и отчёте без post-hoc переоценки метрик.

### Расходы

Все суммы ниже относятся к новым шести profilejobs, включая два rejected
outputs; terminal usage доступен у каждого. Разные tokenizer counts при
одинаковых visible UTF-8 inputs не измеряют денежную экономию.

| Случай | Модель | Input | Output | Cache read/write | Total | Reasoning внутри output | Wall,s |
|---|---|---:|---:|---:|---:|---:|---:|
| Исангулова | GLM | 43764 | 21676 | 0/0 | 65440 | 18317 | 386.52 |
| Исангулова | Sol | 55426 | 3822 | 0/0 | 59248 | 1034 | 77.87 |
| Маслов | GLM | 29818 | 21064 | 0/0 | 50882 | 17680 | 371.20 |
| Маслов | Sol | 42354 | 2776 | 0/0 | 45130 | 773 | 64.86 |
| Ковалёв | GLM | 138343 | 26108 | 0/0 | 164451 | 21485 | 448.19 |
| Ковалёв | Sol | 153402 | 5919 | 0/0 | 159321 | 1552 | 140.50 |
| Все3 | GLM | 211925 | 68848 | 0/0 | 280773 | 57482 | 1205.91 |
| Все3 | Sol | 251182 | 12517 | 0/0 | 263699 | 3359 | 283.22 |

GLM terminal assistant usage: input/output/cacheRead/cacheWrite —
непересекающиеся группы, totalTokens authoritative; reasoning — часть output,
второй раз не добавляется. Native cached input — часть input, reasoning —
часть output. Cache components в этих terminal receipts действительно0;
неизвестные значения не заменялись нулём. GLM три logical jobs, три observed
physical HTTP200, один request/job, retry0. Sol три CLI profilejobs, toolcalls0,
automatic CLI retries0; число скрытых transport requests/retries неизвестно.
Requested config GLM5.3Flash/high и Sol6.1/high; эффективный Pi SDK config
совпадает, фактические backend model/effort обеих сторон не раскрыты.

Денежный расход и actual subscription debit неизвестны (`null`). SDK catalog
cost не является списанием подписки. Account-wide штатная квота:93% по
поручению,92% ранняя проверка,90% перед freeze,89% после run06:53:14UTC.
Изменение account-wide процента не является debit профильного эксперимента:
разработка/reviewer/read-only helpers работали отдельно, их расход не измерен.
Reset-credit/покупки/paid API не использовались. Поиск выключен, экономия
полного коллектора не установлена. На этих трёх inputs GLM суммарно медленнее
(1205.91s против283.22s) и имеет меньший normalization yield; превосходство
качества или денежная экономия из этого эксперимента не следуют.

### Проверки, DoD, сохранность

Перед inference: lint/typecheck,264 unittest/388 pytest,JS20PASS;
web-lint/typecheck/164testsPASS (1skipped), web-buildPASS с canonical URL проекта,
docs-checkPASS с фактическим meta9002. Strict audit frozen826PASS после fix189;
старый auditFAIL остаётся историческим. Встроенный history mount сканирует0
commits из-за worktree path, отдельный read-only frozen826 scan охватил508
commits/no leaks. Критерии/исключения не ослаблялись.

CI checks/web/audit826SUCCESS: actual checkout1fc8a3db4a3cfb5b40a4c4d328d26a5e9b757f0e
имеет parents=[base99bf,head826]; handoff-checkPASS. Эти доказательства относятся
к frozen коду. Итоговый independent review, current CI с actual checkout parents,
handoff-check, SHA-seal и process/write STOP публикуются последним подтверждением
в [PR194](https://github.com/borisboriov/search-for-research/pull/194) после
отчётного коммита; старый PASS не подтверждает новый head.

DoD общего input/provenance/лимитов, terminal run, raw сохранности и измерения
доступных usage выполнен. DoD трёх полностью валидных пар не выполнен: только1/3.
Medium197 оставлен отдельным видимым хвостом; это допустимый технический
partial с явным ограничением, а не доказательство полной готовности метода.
Замороженные source/task/CODE/raw/STOP не исправлялись; следующие calls запрещены.
Предыдущие девять roots и предыдущий partial проверяются по прежним SHA-index;
итоговая read-only проверка всех десяти seals и новый seal фиксируются в PR.

Это три заранее выбранных проблемных development случая, а не случайная
выборка. Совпадение GLM/Sol и source binding не являются человеческим gold.
Полный issue193 не закрывается; merge/deploy/production/продуктовая приёмка
не заявлены. Изменения паспорта не требуются: принятые продуктовые цифры
не меняются. Следующий эксперимент этим этапом не разрешается.

## 2026-10-11: offline фикс #197 и повторная обработка шести saved raw

[Отдельное поручение](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6107053375)
разрешило исправить typed date guard и локально обработать уже сохранённые шесть
raw paired3. Это новая версия **обработки**, без новых ответов моделей или сбора
источников. Предел этапа08:15:33–10:15:33UTC. Sole writer работает в прежней
собственной ветке; cron PAUSED, новых monitor/product messages нет.
[Продуктовая проверка предыдущего partial](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6106563115)
сохранена: замена Sol на GLM и качество nonregression не приняты.

Фикс `b184377842884b3b7f943785de8ca452a4a6069a` вводит processing policy
`fragment-date-v2-orcid-employment-ms`. Guard восстанавливает полный saved
ORCID JSON из согласованных fragments, проверяет длину/textSHA, duplicate keys,
source kind/endpoint и ORCID фиксированного профиля. Для source_metadata
current_affiliation он сначала привязывает ровно один employment-summary к
cited spans put-code/path/organization.name, затем проверяет ровно одно
created-date/last-modified-date.value. Целые13-digit epoch milliseconds
конвертируются детерминированно в UTC; календарная дата сравнивается с указанной
точностью. JSON path определяется пропуском целых sibling values, без поиска
подходящих чисел по всему тексту.

Timestamp произвольного поля, коллекции employments, соседнего employment или
works, строки/boolean/seconds, uncited metadata, иной ORCID и metadata update
после saved checked_at отвергаются. Checked_at — только верхняя граница, не
основание даты и не повышение до current. Поддержан узкий ORCID employment
случай; прочие source_metadata пока unsupported, включая буквальные годы без
типизированного основания. Обычный content literal-year guard, строгие IDs,
spans, source binding и semantic-v3 сохранены. Model schema/prompt не изменены;
raw status/verdict/date/explanation не дополняются.

### Реальные сохранённые inputs и diff всех шести результатов

Новый отдельный root:
`/Users/boris/Experiments/search-for-research/enrichment-orcid-date-offline6-20261011`.
Manifest фиксирует policy/head, parent indexSHA, snapshots точных task/corpus/
raw/receipt и historical normalized/failure каждого случая. Baseline hydrate
загружен из точного Git blob ccde0f9, новые вызовы model/native и network entrypoint
заблокированы. Сам hydrate обеих версий выполнялся реально, без mock результата.
Четыре baseline accepted outputs воспроизведены равными старым normalized,
две baseline причины failure совпали со saved failure. Все raw после обработки
проверены на неизменность. Parent sealed root перед обработкой проверен целиком:
69217 mapped files и indexSHA `a246a34dfae999d0b150df8506586eb590379654653c720a72a433cbc0b0bd94`.

[Generated offline metrics](../../../docs/metrics/enrichment_orcid_date_offline6_20261011.json)
содержат шесть before→after rows, inputs SHA, причины, metadata binding и counts;
публичная проекция не включает сырые адреса. Private metrics/inputs/normalized/
failures/code-snapshots и producing scripts сохраняются в новом root.

| Случай | Модель | До: ccde0f9 | После: новая policy | Причина / граница |
|---|---|---|---|---|
| Исангулова A5089458364 | GLM | Rejected | Accepted4atoms | Typed employment last-modified-date даёт UTC2019-12-11; ложный literal-year отказ устранён. Raw affiliation supported/activity active и их переоценка нынешней актуальности сохраняются. |
| Исангулова A5089458364 | Sol | Accepted4atoms | Accepted4atoms | Input/result/derived и flags равны историческим; контакт undated, affiliation insufficient/activity unknown. |
| Маслов A5054586424 | GLM | Rejected | Rejected | По-прежнему отсутствует profile_assessments.activity.status; schema останавливает раньше date guard. Status из объяснения не додуман. |
| Маслов A5054586424 | Sol | Accepted2atoms | Accepted2atoms | Core равен историческому; контакт historical2007, affiliation/activity unknown. |
| Ковалёв A5054791318 | GLM | Accepted7atoms | Accepted7atoms | Core равен историческому; historical candidate2020, два ORCID не разрешены, HELP2027/current и affiliation/conflicting остаются ошибочными/чрезмерно уверенными оценками. |
| Ковалёв A5054791318 | Sol | Accepted6atoms | Accepted6atoms | Core равен историческому; тот же DOI bridge учтён, personal contact conflicting/coverage0. |

Итог обработки: **4→5accepted из6**, GLM1→2 из3, Sol3→3 из3,
полностью нормализованные пары1→2 из3. Новых профильных jobs0, cumulative35
неизменен; это не новый inference yield и не перезапись исторических метрик
повторного paired3. Четыре ранее принятых результата сохраняют input/result/
derived и flags; новые wrapper поля содержат лишь processing policy/provenance.
Для вновь принятой Исангуловой source/result/derived созданы из неизменного raw,
без новых модельных оценок. Все пять новых normalized содержат исходную
model provenance и отдельную processing provenance с SHA raw/receipt/head.

Конкретный позитивный saved случай: source
`A5089458364-Sb86fd6644a761cd763de`, cited date span fragmentF1500-3300,
object anchorsF3000-4800. JSON path:
`activities-summary/employments/affiliation-group/0/summaries/0/employment-summary/last-modified-date/value`,
object `/0000-0003-0365-8695/employment/8089983`, integer1576026926116 →
UTC2019-12-11T01:15:26.116000+00:00. Calendar information_date2019-12-11
совпала; даты создания/чтения/соседних объектов не подменяют это поле.
Это подтверждает дату обновления employment record, а не нынешнюю занятость.

### Проверки, ограничения и DoD

Регрессии воспроизводят реальные field/put-code/path/epoch #197 в минимальном
синтетическом record без частных контактов. Positive проверяет точный UTC и
неизменность raw/profile assessments;16 negative variants проверяют units,
типы, произвольное число, collection/work/neighbor metadata, foreign profile,
wrong path, uncited field, reading date, future update, unknown date basis и
попытку повысить contact до current. Реальный saved позитив дополнительно
прошёл в offline reprocessing. Прежние ID/span/CRLF/исторические date tests
сохранены.

На fix head lint/typecheck PASS (133files),267 unittest/388pytest PASS,
8skipped/5deselected, coverage94.06%. Начальный запуск make был заблокирован
доступом к существующему uv cache; разрешённый повтор с UV_NO_SYNC использовал
установленный lock, без новых зависимостей. Первый typecheck выявил только
типизацию новых list/dict annotations; исправление прошло полный повтор.
Доказательства strict audit, current CI actual checkout parents, независимого
review и handoff отчётного head публикуются последним подтверждением
[PR194](https://github.com/borisboriov/search-for-research/pull/194).

DoD #197 реализован для документированного bounded employment policy:
реальный saved case и отрицательные object/field/unit/citation/date случаи
проверены, старые strict contracts сохранены. Issue остаётся открытой до
отдельно разрешённого merge; Closes применим только к #197 при подтверждённом
DoD. Полный #193 не закрывается. Финальные SHA-check всех прежних roots,
новый самоисключаемый seal, process0 и write STOP фиксируются в PR.

Новых model/source/search calls0; новые model usage tokens0 как следствие
отсутствия jobs. Денежный расход/actual subscription debit разработки и ревью
не измерены, остаются null; расход прежних шести jobs не переизмерялся и не
прибавлялся второй раз. Human gold0. Guard acceptance не подтверждает истинность
оценок: Исангулова GLM current affiliation/activity чрезмерно уверены; Маслов
не имеет status и его record status не равен person status; Ковалёв GLM
использует future2027/current и категоричное conflicting affiliation,
принадлежность двух ORCID остаётся неизвестной. Nonregression/замена Sol на GLM,
экономия полного collector, merge/deploy/продуктовая приёмка не заявлены.
Следующий эксперимент не запускается; паспорт/productdocs не меняются.


## Практическая передача конвейера и решение по GLM — 11.10.2026

Конечный docs-only этап после принятого offline фикса #197: модельные raw,
исторические результаты, seals и STOP не изменены, новых profile/source/search
jobs0. Существующий `hydrate` реально повторно обработал шесть inputs #197 с
проверкой их SHA/task-corpus binding/raw equality:5 accepted,1 rejected;
Маслов/GLM остаётся без activity.status. Это повторение обработки, не новое
измерение качества или повторный inference. CLIhelp и entrypoints подготовки,
суммаризации и human packets проверены; live/preflight/freeze не запускались.

[Практические команды и файлы](../methods/enrichment_glm_runner.md#практическая-передача-существующих-путей)
разделяют flexible10 с поиском технической Sol-сессии, неуспешный автономный
GLM live, offline3 с новым inference и read-only replay уже полученных raw.
`--mode replay`/`offline-run` вызывают модели и не являются безопасным синонимом
postprocessing. Переданы dependencies/instructions, относительные input paths,
SHA старых evidence roots, существующие Pi12 human cards/CLI и явный пробел
адаптации новых fragment outputs к human packet contract. Рекурсивная копия
старых архивов не создаётся; текущие доказательства содержат лишь changed docs,
CLIhelp/local replay/scoped review/CI и ссылки/SHA прежних корней.

Решение: автономная замена Sol-сессии на GLM не прошла; GLM остаётся только
экспериментальным извлекателем кандидатов с обязательной независимой проверкой
Sol. Готовность полного гибридного pipeline и production readiness не доказаны.
#197 исправляет происхождение даты, не semantic truth; missing status,
переоценка актуальности и неразрешённая атрибуция двух ORCID сохраняются.
Human gold0; деньги/debit/full collector economy неизвестны. Минимальные условия
одного следующего честного e2e контроля перечислены в методике; следующий batch
не назначен. Проверки документов, scoped independent review и current-head CI
фиксируются последним подтверждением PR194. Cron PAUSED; финал — write/process STOP.

## Live3 public collection → GLM candidates → independent full-source Sol — 11.10.2026

**Результат:** один конечный live контроль выполнен; в текущем виде конвейер
**не годен для следующего контрольного batch**. GLM передал3valid packets;
независимый Sol завершил3runtime jobs, после неизменённых semantic-v3/date guards
приняты2packets, только один непустой. Guard отверг ошибочную metadata-дату
Исангуловой; Маслов identity-only без фактов, прежний historical контакт пропущен.
Это диагностический development контроль, не оценка качества на random/gold.

### Постановка, freeze и воспроизводимость

[Постановка до запуска](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6107652850):
только A5089458364/A5054586424/A5054791318; start09:34:36UTC, final deadline
12:34:36UTC11.10.2026. Sole writer в собственной ветке PR194. Cron PAUSED.
До freeze offline fullpath fixture прошёл tool IDs→literal binding→prepare→
independent Sol boundary→semantic/date guards, включая невыбранный контекст,
identity-only, missing status, invented IDs, tampered source и full-input cap.
Независимый reviewer обнаружил продолжение после incomplete GLM runtime;
исправление `usage_complete` и тест отсутствия следующих jobs проверены до live.

Один новый root:
`/Users/boris/Experiments/search-for-research/enrichment-live3-independent-sol-20261011`.
Freeze09:57:21UTC, executed head `dd6cbbcb2235dd82d153dd18e16946ea53e013c5`.
Acquisition STOP10:12:36UTC; шесть jobs, cumulative35→41, без retries/repair/Astra/
paidAPI/reset/purchases/accountchanges и без developer URL/search assistance.
Метод/лимиты после freeze не менялись. Старые raw, метрики и roots не перезаписывались;
новый root хранит лишь собственные artifacts и refs/SHA13предыдущих index,
включая последнюю docs передачу. Их index SHA проверены; полного повторного
обхода86тыс.старых файлов и рекурсивного копирования этого этапа не было.

Seeds сверены по SHA и whitelist исходного flexible10 catalog sample: id/name/
institution/institution_id/ORCID/h_index/cohort/suspect_merge. В collector task
нет прежних pageURLs/email/verdicts/bodies. Все source choices принадлежат GLM
через nativeZai/DDG actual rows и observed href; snippets не стали evidence.
Raw/rendered тела и точные source/fragment/value IDs сохраняются; код связывает
value по offsets. Sol получает ровно GLM items и все fragments всех checked
live bodies. Sol input/code/source-record/body/text/prompt/receipt SHA приведены
в [generated metrics](../../../docs/metrics/enrichment_live3_independent_sol_20261011.json)
и private transfer index; guards повторно сверили весь saved corpus.

| Случай | GLM candidates | Saved sources/fragments; data prompt bytes | Sol и принятая часть |
|---|---|---|---|
| Исангулова A5089458364 | 6: personal_contact,3topic,supervisor_role,city | 4/54;162885 | Raw contact supported/undated; city2019-12-11/source_metadata. Весь packet rejected `Unsupported metadata date object`, accepted atoms0 |
| Маслов A5054586424 | 0; identity evidence есть | 3/104;387998 | Identity supported, current_affiliation insufficient, activity insufficient/status unknown; accepted identity-only, atoms0 |
| Ковалёв A5054791318 | 3: personal_contact,2topic | 4/106;275388 | Все3usable по Sol; контакт undated, topics undated; identity/current_affiliation supported, affiliation date unknown, activity supported/active2026-05-22/content |

System rubric instructions дополнительно10088UTF8bytes/person: полный вход с
ними172973/398086/285476bytes, усечения не было. Sol процитировал7/5/5refs вне
union refs выбранных GLM items/profile evidence; items не добавлял. Это
независимая проверка GLM candidates, не ещё одно параллельное извлечение.
Профильный отказ Исангуловой сохранил untouched raw/receipt и разрешил остальные
независимые случаи. #197 поддерживает source_metadata только для оси
current_affiliation и конкретного cited ORCID employment created/modified field;
metadata city неподдержана. Правило не ослаблено; raw/status не исправлены.
Не было quota/common runtime/method failure; terminal reason `finite_live3_complete`.

У Исангуловой raw Sol current_affiliation supported без даты и activity active2024
не становятся принятыми фактами или доказательством нынешней занятости. У
Ковалёва supported identity относится к этому4source корпусу и не разрешает
исторический конфликт двух ORCID в более широком корпусе. Поддержанный формат
и literal year guard не доказывают правильную семантическую атрибуцию даты.
Личный набор/готовность руководить не подтверждены ни в одном случае;
новый недатированный контакт не доказывает доставляемость или готовность.

### Отдельное posthoc сравнение пропусков

После acquisition STOP сверены SHA трёх прежних Sol normalized #197 и трёх
flexible10 collector outputs. [Generated comparison v2](../../../docs/metrics/enrichment_live3_posthoc_comparison_v2_20261011.json)
хранит только hashes адресов, old verdict/date и наличие literal в новом corpus/
GLM selection. Прежние модели не являются human truth; это не recall benchmark.

Прежний undated contact Исангуловой и historical2007 contact Маслова отсутствуют
в новых bodies и не выбраны. GLM Исангуловой нашёл другой адрес на странице
кафедры НГУ; он остаётся candidate из-за rejected Sol packet. Для Маслова
ни один из5old flexible literal candidates не появился в новом corpus. У
Ковалёва прежний conflicting/historical2020 candidate отсутствует; из8old
flexible literals один есть в новых bodies, ни один не выбран. Выбран новый
недатированный персональный контакт на actual observed странице embodied-ai.
Количество sources old→new:4→4,4→3,10→4; состав различается. Нельзя объявлять
изменение precision/recall или разрешение исторической неоднозначности.
Первый unsealed private posthoc draft ошибочно называл fragment count
`old_sources`; он сохранён с correction note. Authoritative v2 вычисляет unique
source_id и отдельно fragments. Модельные/source результаты не менялись.

### Usage, проверки и границы решения

GLM5.3Flash/high requested через штатный Pi/Zai, Sol6.1/high requested через
native CLI/openai. Фактические backend/model/effort runtime не раскрывает;
requested configs, receipts, untouched raw и distinct native agent IDs сохранены.
3GLM+3Sol logical jobs;28observed GLM model requests (6/11/11),27sourcecalls
(7/11/9),10shared search reservations (8nativeZai+2DDG),22HTTP started/reserved
включая robots/redirects. Sol physical requests/transport retries не раскрыты;
automatic CLI/job retries0. Caps остались≤12requests/600s/24sourcecalls/4search/
20HTTP/person, shared search≤12/HTTP≤60,Sol≤900s/full JSONprompt≤1MB/person.

GLM:181928fresh input+204864cacheRead+19090output=405882tokens,cacheWrite0;
reasoning не раскрыт, к output не прибавлялся. Sol:232574input+8161output
=240735tokens,cached_input0 (cache — часть input). Runtime wall sums:
GLM672.264s,Sol222.464s; это не время полного development/review этапа.
Official account remaining85%09:56:49UTC→84%10:13:10UTC; один accountwide процент
не приписан run и не переведён в деньги. Денежный subscription debit, фактический
billing, development/review tokens/cost и экономия полного сбора неизвестны.
SDK/catalog cost не выдан за списание подписки; unknown не заменён нулём.

Adapter checks:20targeted tests,274unittest,388pytest (8skip/5deselect,
coverage94.06%),lint/typecheck PASS. Strict audit штатной целью PASS; локальная
Docker git-history строка worktree сама не доказательство, поэтому полная
история проверяется отдельно с readonly mount common gitdir. Docs-check,
независимый scoped recheck результатов и actual checkout/parents CI последнего
head фиксируются в финальном review-комментарии PR194 и transfer evidence.
Ни production/productdocs, ни merge/mainpush/deploy не менялись; #193 остаётся
открытым, #197 сохраняет прежний bounded DoD до отдельно разрешённого merge.

DoD этого контроля — три live попытки и три независимые проверки либо явные
skip/refusal, immutable inputs/raw/receipts, полные sources/IDs/SHA, отдельные
candidates/verdicts и честные usage/limitations — выполнен. Устойчивый pipeline
не доказан:1/3непустых accepted chains, date отказ и пропуск saved2007 контакта.
Решение: **текущая конфигурация не годна для следующего контрольного batch**;
исправлять output вручную, повторять эти jobs или начинать новый batch эта
постановка не разрешает. Human0/Solnotgold, deliverability unknown, current
readiness unknown. Все наблюдавшиеся собственные process PID завершились;
cron PAUSED, acquisition/model/source STOP, окончательная передача — write STOP.

## Конечный offline partial этап 11.10 после продуктовой проверки live3

Постановка: [PR194 scope](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6108233916),
основание — [продуктовый разбор live3](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6108183785).
Окно 10:45:39–12:45:39 UTC, только offline. Model/source/search calls0,
cumulative41→41, human gold0. Разработка и необходимое независимое ревью через
текущую Codex подписку отдельно; их usage/debit неизвестны, не объявлены нулём.
Ни исправлений raw от модели, ни новой профильной inference не было.

### Один freeze и неизменённые входы

Новая policy `live-sol-partial-dates-v1` зафиксирована на
`c037503be71105e79b92bbee6b06d7abc427f467` после offline tests; новый приватный root
`/Users/boris/Experiments/search-for-research/enrichment-live3-partial-offline-20261011`.
Manifest SHA `b1573cfe61fd1186b4b3e5f2fa28f8825a6c3540466e9cd8af5ec87cbd98afdb`.
Freeze один, replay трёх прежних Sol ответов один, retries0. Runner требует clean
committed code, новый root, deadline≤2h и exact old seal. Старый live3 index SHA
`83629e8ed2eb537fead733abbce434e953beb9f2e82eedd5f3fc0635e6e0b814` проверен по
всем655 файлам; все checked source bodies заново восстановили точно тот же corpus.
Прежние raw/task/schema/corpus/input/receipt скопированы byte-for-byte с SHA,
прежние accepted cores/rejection reason воспроизведены до сравнения.

Новый архив содержит только новые inputs/processing/metrics/code/scope/proofs и
14 ссылок SHA старых indices; старые архивы не копируются рекурсивно. Все прежние
sealed roots, raw/normalized/metrics/STOP неизменны. Исторический live yield2/3
не заменён offline результатом. Полные raw model summary/verdict/status сохранены.

### Результат и контракт принятой части

[Generated diff](../../../docs/metrics/enrichment_live3_partial_offline_20261011.json)
получен кодом из saved inputs, не ручной переписью показателей.

| Случай | Прежняя обработка | Новая обработка | Validated/rejected/usable atoms |
|---|---|---|---|
| Исангулова A5089458364 | rejected whole packet,0 usable | partial,не full success | 5/1/4 |
| Маслов A5054586424 | valid identity-only,0 atoms | identity-only без изменений | 0/0/0 |
| Ковалёв A5054791318 | accepted3atoms,3usable | accepted,классификации сохранены | 3/0/3 |

У Исангуловой локально отклонён только city atom
`A5089458364-Sb86fd6644a761cd763de-F3000-4800-text` с raw date2019-12-11/
source_metadata: прежняя причина `Unsupported metadata date object`. Дата не
переписана на unknown и guard #197 не расширен. Literal contact и3topic проходят
исходные независимые assessments и guards; supervisor_role валиден по формату,
но остаётся unusable по field_verdict. Это4 usable atoms, не5 и не6.

Полные strict schema/task IDs/source binding/literal spans/semantic-v3/provenance
остаются общим gate. Profile identity должна быть supported; иначе все atoms
blocked. Любая ошибка profile date guard также блокирует всё. Only atom-local
date failures изолируются. Отказы имеют явные validation_status/reason и
effective usable_coverage=false. Missing activity.status не достраивается.
Shared/schema ошибки не salvage; raw summary не становится summary принятой части.

Новый wrapper отдельно хранит original/effective classifications, profile gates,
counts, fully_validated/fully_accepted_nonempty и untouched raw_result; legacy
ключа result нет. Partial записывается в partial-verdict.json, а не verdict.json,
поэтому downstream не получает его как полный успех. Empty valid→identity_only,
all-invalid→rejected; 2full-valid packets (один пустой) и1partial не названы3/3.

Undated personal_contact не доказывает current applicability/доставляемость.
Сохранившиеся model оценки profile affiliation/activity не доказывают нынешнюю
занятость или готовность руководить. ORCID конфликт Ковалёва из старого широкого
корпуса не разрешён. Human0; precision/recall, nonregression, economy и production
готовность не измерены и не заявлены.

### Маслов: где закончился путь к историческому контакту

[Generated saved trace diagnosis](../../../docs/metrics/enrichment_maslov_trace_offline_20261011.json)
сверяет seeds, requests/responses, actual native title/link rows, observed hrefs,
saved sources, последний actual GLM model payload и untouched collector output.
По каждому использованному файлу хранится SHA из старого index. Baseline #197
normalized/corpus проверены по своему sealed index; это posthoc материал, не
подсказка live сборщику. Старый contact был historical2007/content на сохранённой
[статье D-Lib](https://dlib.org/dlib/november07/phillips/11phillips.html), а не
current контакт доказанно этого MEPhI профиля. Его literal в новых bodies отсутствует.

Seed: Alexey Maslov, MEPhI, ORCID0000-0001-7196-1640. Первый read ORCID с query
Alexey Maslov вернул fragments содержащие A New Face for DSpace и DOI
10.1045/november2007-phillips. Эти title/DOI есть в последнем фактическом model
payload; metadata не потерялись при передаче. Далее четыре actual queries:

1. Native Zai: Alexey Maslov ORCID 0000-0001-7196-1640.
2. Native Zai: Алексей Маслов МИФИ доцент кафедра.
3. Public DDG: "Alexey Maslov" "MEPhI" — robots refusal.
4. Native Zai: "Маслов" НИЯУ МИФИ сотрудник аспирантам.

Ни одного publication title/DOI query. Native raw rows содержали корни сайтов;
код зарегистрировал именно их, а не обрезал точные URL локально. D-Lib не было
среди этих links или returned observed hrefs. Прочитаны3bodies: ORCID, mephi.ru,
voip.mephi.ru (104fragments всего); D-Lib не запрашивалась и не читалась. На
voip queries Маслов Алексей/Маслов//api вернули0matching fragments, а ссылки
с mephi.ru на home.mephi.ru/ru/people встретили robots refusal. Две попытки
Semantic Scholar URL отклонены как unregistered. Отказ не обходился.

Collector selections пусты, сохранена только identity evidence. Доказанный
разрыв — **discovery/source acquisition исторической статьи**: её metadata
GLM видел, её URL/body/contact не видел. Нельзя приписать модели неправильную
оценку контакта в непрочитанной статье. Изменить ли queries/priority под
историческую работу — вопрос стратегии; доказанного локального parser/binding
bug нет, поэтому дополнительный фикс источников не внесён.

Следующий контроль, **не запущен**: отдельный finite freeze резервирует один
из4search queries для observed ORCID title/DOI. Только actual result URL/observed
href может привести к checked article body; baseline page URL не инжектировать.
Доказательства: search row/href→body/SHA→literal candidate→independent Sol
semantic/date assessment. Отдельно учитывать search absence/refusal, source
acquisition и interpretation; historical2007 и ambiguity MEPhI/Texas A&M
сохранять. Unknown: выдаст ли такой запрос ссылку, подтвердится ли личность,
выберет ли collector контакт. Это требует отдельного разрешения/постановки.

### Проверки, DoD и завершение

25targeted adapter tests;279unittest;388pytest,8skip/5deselect,coverage94.06%.
Lint/typecheck/docs-check PASS; make audit --no-images --strict PASS. Actual
common git history отдельно проверена readonly Docker mount:516commits,no leaks.
Meaningful cases: valid contact+rejected metadata city; common identity/author/
source/provenance/schema/span/ID/profile-date failures; receipt SHA mismatch;
all-invalid/empty/previous valid; partial file не legacy verdict; saved replay
без model/HTTP, no overwrite; прежние malformed schema/dates/IDs/spans checks.
Реальный Isangulova raw preflight подтвердил5validated/1rejected/4usable и
untouched raw SHA до freeze. Scope, freeze/code SHA, новая обработка3raw, старый
vs новый diff, trace diagnosis и ограничения сохранены. Независимое ревью и
CI с actual checkout/parents текущего head — в финальном комментарии PR194 и
приватном transfer index. Процесс offline replay terminal STOP; cron PAUSED.
Новый batch/merge/mainpush/deploy/productdocs не выполнены. После финальной
передачи — own process/write STOP; продолжение отдельно не назначено.

## Заключительный publication/DOI control 11.10.2026 и решение по GLM

По [прямому разрешению на один контроль](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6108525639)
проверен targeted positive control Maslov A5054586424/ORCID0000-0001-7196-1640.
Anchor A New Face for DSpace/10.1045/november2007-phillips заранее выбраны кодом
и постановкой из сохранённой публичной work metadata; это не автономный выбор
работы GLM и не случайная выборка. Старые article URL/body/email/verdict не
передавались collector и не импортированы как новые источники.

Freeze выполнен на `b75750c3ae3a66417341dee720e31072fec9ece6` в новом root
`/Users/boris/Experiments/search-for-research/enrichment-publication-control1-20261011`.
Start11:23:56UTC/deadline13:23:56UTC включает подготовку и передачу. Прежние
caps4search/20HTTP/24sourcecalls/12modelrequests/600sGLM/900sSol, Sol prompt≤1MB;
один GLM5.3Flash/high Pi collector и один полный native Sol6.1/high verifier,
cumulative41→43. Astra0, автоматических retry/repair/newbatch0, reserve0.

### A/B/C и действительный путь источников

[Generated trace/metrics](../../../docs/metrics/enrichment_publication_control1_20261011.json)
получены из frozen manifest, actual tool requests/responses, checked bytes,
GLM/Sol raw, receipts и terminal STOP, без ручного редактирования модельных выводов.

| Критерий | Исход | Доказательство и граница |
|---|---|---|
| A discovery/acquisition | **fail** | Fresh ORCID200 подтверждает exact title+typed DOI, put-code10435134; первый actual native query точен. Ни target article body, ни target URL/observed article redirect не получены. |
| B literal extraction | **pass** | Один topic candidate, code binding actual source/fragment/value ID+offsets прошёл. Он из другой ORCID работы2009, не из непрочитанной статьи2007; contact0. |
| C full independent Sol | **pass** | Ровно1GLM candidate и весь новый корпус2sources/36fragments; strict schema,4task IDs, input/raw/receipt SHA, semantic-v3 и неизменённые date guards прошли. Не параллельное самостоятельное извлечение. |

Fresh ORCID read11:42:37UTC: bodySHA
`82b4b7906f8b62b0b5b7f4a4bfc7aaa3891f5d67309175c89d0232b82b098ea7`.
SHA совпадает с прежним публичным record, но новое HTTP200/checked_at подтверждены
новой receipt; сохранённое тело не подставлено. Первый reserved/native query
11:42:49UTC: `"A New Face for DSpace" "10.1045/november2007-phillips"`.
Actual search link rows содержали частичные пути D-Lib и других сайтов, не точный
URL целевой статьи. GLM не прочитал D-Lib source.

GLM попытался отдельный HTTPS DOI resolver. Единственный его HTTP — robots.txt:
status301; код отказал `No full allowing robots` до HTTP чтения статьи. Redirect
robots не объявлен redirect к статье; отказ не обходился. Это ограничение
конкретного acquisition route/guard, не доказательство недоступности статьи вообще.
Остальные3nativequeries GLM выбрал сам: имя+МИФИ, имя, имя+DSpace repository.
Прочитан mephi.ru200, bodySHA
`f72f2c15cd730b8bedb750ca697546b780dbc2bc2591b7319f3710641a4b60bc`;
главная страница не устанавливает персональную аффилиацию. Дополнительная попытка
DDG до обязательного query отклонена кодом; HTTP/search для неё не начат.
Эти2tool refusals сохранены отдельно от валидного binding и Sol результата.

Candidate `A5054586424-Sdde198632266a734378a-F3000-4800-text` — буквальное окно
ORCID3000–4800 с названием Adding OAI-ORE Support to Repository Platforms.
Sol использовал полный корпус, включая продолжение даты, и классифицировал
topic historical2009-05-18, usable1. Raw SHA
`f9031650815a9bcbac63fc1f3fc1f6b6bace0f12379c7a793ab771d7d09563ac`.
Identity supported по exact ORCID; current affiliation/activity insufficient,
activity status unknown. Human gold0. Это техническая модельная оценка, не ручная
истина; MEPhI/TexasA&M ambiguity не разрешена, принадлежность отсутствующего
контакта не установлена. Unknown/conflicting identity тоже была допустима для C:
требование supported не использовалось как критерий успеха контроля. Консервативная
общая identity dependency processing policy не ослаблена.

### Расход и остановка

| Профильный job | Фактический usage | Wall, s |
|---|---|---:|
| GLM Pi |8requests; input43298 + cacheRead21120 + output8855 = total73273; cacheWrite0 |261.628 |
| Full independent Sol |input42513/output1408 = total43921; cache0; reasoning291 уже внутри output |47.159 |

Итого profiletokens117194/wall308.787s;4native search/8source toolcalls/4HTTP
reserved и started (ORCID, DOIrobots, MEPhIrobots, MEPhIbody). Логические jobs2,
cumulative43; preflight probes0inference не profilejobs. Sol toolcalls0;
внутренние physicalrequests/backend/effective model Sol не exposed, requested
OpenAI/gpt-6.1-sol/high подтверждены. Денежная стоимость/реальное профильное
списание unknown, не0. Official accountwide weekly остаток82%11:29:32UTC→81%
11:48:35UTC; изменение включает разработку/ревью/другую активность и не измеряет
расход именно этой пары. Developer/reviewtokens отдельно не exposed.

Execution terminal STOP11:47:34UTC, без runtime failure. Старые655mapped live3
и77mapped partial files заново сверены; SHA/raw/метрики/STOP не переписаны.
Новый root содержит новые evidence и refs старых индексов, без рекурсивного архива.

### Проверки и окончательное решение

26targeted adapter tests/280unittest/388pytest,8skip5deselect,coverage94.06%;
lint/typecheck/docs-check и strict audit PASS. Local Docker history summary
0commits/fatalnotrepository отдельно не засчитана: actual read-only common Git
history scan519commits/no leaks, плюс currentCI audit. Initial actual Pi probe
использовал старый manifest fixture; исправленная current-shaped fixture проверила
20currentcodeSHA/caps41→43/oneprofile и actualPi0model/source/search4.175s.
Actual frozen root probe2.946s тоже0inference. Первоначальная подготовка fixture
завершилась FileNotFound до Pi, сохранена как инженерная ошибка, не скрыта.
Независимый pre-live reviewer PASS0findings сверил freeze/request/CI mergeparents;
финальные review/currentCI/handoff и transferSHA — в финальном комментарии PR194.

Первый live запуск остановила автоматическая approval проверка до process/jobs:
сочла отсутствующим явное согласие на payload/recipients. Повторно прочитано
доверенное разрешение Бориса «Давай» и соответствующее поручение одного публичного
GLM→Sol контроля. То же прямое действие после этой проверки разрешено; обхода,
смены транспорта или дополнительных live попыток не было.

**GLM автономный поиск для каталога не принимаем:** A не прошёл даже для одного
известного targeted anchor. B/C показывают работоспособность буквального binding
и полной независимой проверки уже прочитанного ORCID, но acquisition gap не
устраняют. Это не универсальный вывод о модели или поиске вообще: границы —
конкретные tools, search responses, robots policy и единственный кейс.

Рекомендуемый fallback — ранее успешный **Sol-assisted поиск + обычный код +
независимая проверка**, с ручным контролем; универсальный автономный CLI,
массовое покрытие, экономия и production readiness не доказаны. Fallback не
внедрён и не запущен. GLM оставить экспериментально там, где есть доказательство
пользы. Экспериментальное сопровождение этой гипотезы закончено: никакой следующей
десятки/минираунда/monitor/followup. Cron PAUSED; merge/mainpush/deploy/productdocs
не выполнялись. Итоговая передача — собственные процессы/запись STOP.

## Sol-assisted workflow и baseline contact cards — 11.10.2026

По [новому offline scope PR194](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6108925959)
закреплён переносимый контактный процесс и подготовлен отдельный human packet.
[Контракт/минимальные команды](../methods/enrichment_glm_runner.md#sol-assisted-контакты-переносимый-offline-tested-workflow-11102026)
разделяют явный поисковый шаг Sol-агента и автоматические стадии имеющегося кода.
CLI не предоставляет search tool; записанный план наблюдённых URL не доказывает
физические search calls. GLM0, новых profile model/source/search calls0,
cumulative43 неизменен. Cron PAUSED, следующий batch/monitor не разрешён.

`scripts/enrichment_assisted.py` использует PublicLoader, буквальный binder,
полный checked static corpus, отдельный native Sol6.1/high и прежнюю semantic-v3.
Добавлены явные freeze/deadline/model/HTTP/prompt caps, single writer lock,
запрет повторения unknown attempts, reuse только сверенных raw/receipt/input/
source bindings. Date gate обязателен до cards; raw failures остаются неизменными.
HTML/ORCID/PDF и literal MathNet decoder переиспользуются; общего crawler,
универсального рендера, платного API и GLM fallback нет. Контактный collector
поддерживает непрерывный контекст и пробелы вокруг `@`; остальные18полей полно
не собирает. Fresh live end-to-end с новым CLI **не запускался**.

Новый локальный root `enrichment-sol-assisted-offline-20261011` содержит packet
`human-v3/packets/baseline-contacts/review.html`, полную manifest связь45atoms,
`entries.json`, `offline-progress.json`, frozen offline fixtures и инженерные
proofs. Выход создан из unchanged flexible10: baseline index SHA
`051331260c38f35cadbf3580cbddec217710a00550dde97791b73b36bdc251fc`, проверено865mappedfiles;
legacy parser archive index SHA
`a8413a08783b48e56fb46e5b9e4710c16a5d3b8bd63aa19683f9f2e75154dd85`, проверено1316mappedfiles.
Исторический parser принимает только4allowlistedPDF и проверяет собственные SHA;
новые PDF им не читаются. Старые roots/STOP/metrics не переписаны.

[Агрегаты](../../../docs/metrics/enrichment_sol_assisted_offline_20261011.json) сгенерированы
из actual saved wrapper receipts и manifest:10профилей,8selectedcontacts,
3historical/5undated,2безпринятогоконтакта. У каждой карточки есть имя/ID/вуз,
точный URL, буквальный фрагмент/полный сохранённый контекст, принадлежность,
датированность и ограничения/конфликты. Длинный контекст раскрывается без
удаления текста; навигация показывает все10профилей. Для двух непринятых случаев
показаны причины отказа кандидатов, отсутствие контакта не утверждается.

Пакет не содержит предзаполненных человеческих решений. Selected-contact режим
старого human_answers_v3 требует отдельные text/identity/current ответы;
uncertain допустим, unknown нельзя заменить согласием автоматически. Export
связан с packet SHA; importer отвергает скрытые/повторные claim IDs, отсутствие осей
и чужой packet. Реальные будущие answers импортируются отдельно. Проверка8контактов
не принимает45atoms или целый профиль; contact≠student intake/deliverability.
Human records0/human_reviewed0, прежние Znamenskaya/Parkhomchuk/Shumeyko,
Pi12/live3/remaining6 assessments не смешаны с этой приёмкой.

Исторический native usage flexible10:459511input+output tokens/645.630s wall
для10jobs. Это прежний расход, не новая цена workflow. Поиск ведущего Sol,
разработка/ревью, общий подписочный debit и dollars остаются unknown/null;
ни API pricing, ни ноль не подменяют стоимость подписки.

14meaningful mocked pipeline tests покрывают prepare/freeze/dry-run, неправильные
планы, полный source context, literal whitespace/renderer, SHA tamper, receipt
reuse, STOP/lock/unknown no-retry, quotas/deadlines/full prompt cap, date failure
и selected human import. Real saved export подтвердил10articles/8contactsections;
JS export исполнен на synthetic in-memory ответе: no answers и missing axes
блокируются, three-axis uncertain export связан с правильным SHA; реальный
human result не записан. Browser UI visual inspection недоступен: политика
отклонила file URL, обход не выполнялся. Структура/код экспорта проверены; внешний
вид в настоящем браузере остаётся пределом проверки.

Подготовка/dry-run/status фактического offline fixture повторены без calls;
`live_authorized:false` предотвращает случайный будущий запуск. Initial fixture
ошибочно пометил скопированный PDF как MathNet derivative, validation остановила
его до calls; исправленный plan сохранён отдельно. Initial PR scope publication
отклонила автоматическая approval проверка из-за payload/consent; доверенное
разрешение Бориса повторно сверено, локальные пути/internal IDs убраны, тот же
PR comment разрешён. Смена транспорта/обход/дополнительные profile jobs не было.

Локальные make lint/typecheck/docs-check PASS, 294unittest и388pytest PASS
(8skip/5deselect), coverage94.06%; strict audit без images PASS. Отдельное
сканирование actual common Git history, независимое ревью конкретного head, актуальный
CI merge/base/head и окончательный transfer index/process-write STOP фиксируются
в итоговом комментарии PR194. Вне результата остаются свежая live проверка нового
CLI, человеческая приёмка и измерение полной assisted экономии; старые метрики
не превращены в новый quality score. Merge/mainpush/deploy/productdocs не выполнялись.

## Sol-assisted live3 и четыре человеческих вопроса — 11.10.2026

По [постановке этапа](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6109566149)
проверен реальный переносимый workflow на трёх заранее выбранных профилях
frozen10: Maslov A5054586424 (historical), Ledovskaya A5042154547 (undated),
Styrin A5047877230 (без принятого контакта). Выбор/sample/сравнение и конечный
бюджет зафиксированы до поиска в новом частном root
`enrichment-sol-assisted-live3-20261011`. Знакомая выборка проверяет регрессию
работоспособности; это не слепой тест качества нового каталога.

**Решение: live цепочка прошла на всех трёх профилях.** Новый Sol-assisted поиск
→ observed URL plan → prepare/dry-run/run → реальные публичные источники →
буквальные кандидаты/полный корпус → отдельный native gpt-6.1-sol/high с полной
рубрикой → source/raw/schema/date guards → карточки. В первоначальном проходе
3/3 validated outputs, 2 выбранных контакта и один содержательно отрицательный
результат. Пустое покрытие Styrin не является техническим отказом. GLM/Astra
профильных jobs0, исправительных profile jobs0, unknown started jobs0,
автоматических повторов0; provider transport retries не раскрыты.
Поисковый шаг остаётся явным агентским; универсальный автономный CLI не доказан.

### Человеческие ответы и UX

До этого этапа Борис реально экспортировал и импортировал восемь baseline
contacts: text agree8/identity agree8/прежний current uncertain8. Его пояснение:
не знает, как проверить актуальность. Это подтверждение двух осей восьми
контактов, не приёмка восьми профилей или всех45atoms. Ответы с именем/заметками
остались частными. Повторный импорт настоящего файла текущим importer дал
запись, идентичную уже сохранённой; SHA исходного answers/record/старого packet
сохранены. Прежний current не переинтерпретируется как согласие с исторической
датой и не становится подтверждением актуальности.

Новые контактные packets/answers/records v4 разделяют text, identity,
**source_date** и **current**. Дата/без даты/исторический источник — отдельный
вопрос от наличия доказательства актуальности сейчас. Не требуется писать
учёному, проверять SMTP или самостоятельно доказывать актуальность.
«Недостаточно оснований» допустимо и не подтверждает current. Исправление
категории явно необязательно. Текущий официальный список сотрудников даёт
основание для affiliation на observed_at; доступная персональная страница
может быть старой, публикация email не доказывает доставляемость или набор.

Схемы и каталоги v4 явные, importer сохраняет совместимость со старым v3;
смешанные версии/скрытые claims/пропущенные обязательные оси отвергаются.
В human_metrics старый смешанный вопрос учитывается как
`legacy_contact_current_v3`, отдельно от новой current оси. Общие packets v3
не менялись. Новых фактических v4 human answers0, предзаполненных решений0.

Actual native question оказался обращён владельцу адреса и спрашивал текущую
применимость. После live он заменён в UI вопросом к проверяющему о приведённых
доказательствах. Frozen native raw/results/cards не переписаны; final baseline
и live3 packets отдельно пересозданы без новых вызовов. Live run выполнен на
code head7b9a104ffa8831fdc219357a7f7a6abe94ac1a59; финальное изменение касается
этого UI вопроса, не acquisition/model/rubric/guards. Код freeze сохранён.

### Сравнение по профилям

[Агрегаты](../../../docs/metrics/enrichment_sol_assisted_live3_20261011.json) получены из
actual receipts, literal inputs/results и private сравнения, без адресов/имени
человека. В локальных final cards сохранены URL, цитаты, полные контексты,
source/raw/input SHA, оси личности/поля/даты и provenance.

| Профиль | Новый материал и результат | Сравнение с baseline и human | Affiliation / current / readiness |
|---|---|---|---|
| Maslov | D-Lib + новый public ORCID; 5 кандидатов, 1 usable личный контакт; дата2007/content, historical | Точное совпадение прежнего контакта, human text/identity agree; утраченных/новых принятых0 | Identity supported по источникам/ORCID; нынешняя affiliation insufficient, active unknown. Каталог МИФИ конфликтует с Texas A&M/Manakin контекстом; нынешний работодатель не установлен. Current/readiness не подтверждены. |
| Ledovskaya | Официальный chemstaff СПбГУ; 1 кандидат/1 usable; undated/unknown basis | Точное совпадение прежнего контакта, human text/identity agree; утраченных/новых принятых0 | Identity/affiliation supported, active supported; observed_at13:43:28UTC. Страница говорит «с2024 по настоящее время», но дата обновления и нынешняя актуальность email неизвестны. Readiness не установлена. |
| Styrin | Официальный digitlab staff ВШЭ; 1 кандидат/0 usable; адрес в блоке контактов лаборатории, personal field insufficient | Baseline тоже0принятых; overlap с human-confirmed8 отсутствует. Новый кандидат не human-reviewed | Identity/affiliation supported, observed_at13:44:22UTC; active unknown. Лабораторный адрес не автоматически личный контакт, current/readiness не установлены. |

Overlap с человеческими ответами касается **только двух** выбранных baseline
контактов; повторная человеческая проверка8/8 не проводилась. Новые результаты
не human gold. Maslov source identity supported не доказывает правильность
текущей каталожной affiliation; конфликт оставлен видимым, профиль не исправлялся.
Сборщик здесь контактный: отсутствие claims про набор не является доказательством
отсутствия готовности руководить или полноты остальных18полей.

### Расход, бюджет и сохранность

Конечный бюджет13:30:19–16:30:19UTC: search≤30, sourceHTTP≤90/30perprofile,
profileSol≤6 (3initial + максимум1после конкретного исправления/профиль),600с/job,
remaining_stop0 прямо разрешён. Все три initial jobs завершились существенно
раньше deadline; дальнейшие calls остановлены. Новых профильных jobs3,
**cumulative43→46**, без новых платных API, покупок, reset или смены аккаунта.

- Явный отдельный Sol/high search:26logicalqueries/11webtoolcalls,
  13open/5click/5find,13:33:42–13:37:16UTC. Агент не читал baseline URL/email/ответы
  и не писал файлы. Observed plan не скопирован из baseline. Это агентский
  discovery ledger, не независимый physical transport receipt. Webbackend
  HTTP/tokens/cache/debit unknown; общий физический HTTP с этим backend не измерен.
- PublicLoader:7reservations/7finished/7physicalHTTP, все200;3robots +3HTML +1ORCID.
  Request wall sum6.884с, unknown reservations0; initial fresh root, reuse requests0.
  SourceHTTP cap соблюдён. Роботный отказ DBLP/pid при поиске не обходился;
  web Internal Error не назывался доказанным403/robots отказом.
- Native Sol:90254input +5888output =96142tokens; cached0/cachewrite0.
  Reasoning2024 уже включён в output, не прибавлен второй раз. Wall sum191.929с:
  Maslov81.941, Ledovskaya46.532, Styrin63.457. Requested model/effort6.1-sol/high
  сохранены, backend metadata не раскрыты; tools0, отдельные ephemeral contexts.
- Official account-wide remaining77%→76%; включает разработку/поиск/другую
  активность. Это не точный debit трёх профилей. Development/review/search usage,
  фактические деньги и stage debit unknown/null.

Заново сверены68mappedfiles предыдущего offline seal, baseline865 и historical
legacy1316mappedfiles:0расхождений; реальные answers/record прежние. Прочие старые
архивы не копировались рекурсивно и не выдавались за заново целиком проверенные.
Новые материалы, receipts, raw, packet, private сравнение и инженерные logs
хранятся в новом root. Собственные initial fixture/инженерные ошибки не стали
profile jobs: первый сбор агрегатов ошибочно искал seconds в ledger, затем взял
actual request receipts; старое сравнение и результаты не переписаны.

### Проверки и границы приёмки

15targeted assisted tests и8human tests PASS; synthetic in-memory JavaScript
export actual final HTML для8baseline/2livecontacts проверил пустые/пропущенные
ответы и четырёхосевой export с правильным packet SHA. Это не реальные human
answers. Real v3 export/import совместимость подтверждена настоящим answers
файлом. Визуальный browser UI по-прежнему не проверен; прежний file URL policy
отказ не обходился.

AGENTS lint/typecheck/docs-check PASS;295unittest/388pytest PASS
(8skip/5deselect,coverage94.06%). Strict audit без images PASS; актуальные
независимое review/base/head, CI, readonly handoff и окончательный SHA seal
фиксируются в финальном комментарии PR194. Docker gitleaks из worktree не прочитал
общую Git-историю (0commits/fatal) и не засчитан доказательством; actual common
Git readonly отдельно проверен тем же pinned инструментом:522commits/no leaks
до заключительного коммита; CI и staged scan проверяют финальное изменение.

Live доказал работоспособность этой цепочки на трёх известных профилях;
массовое покрытие, слепое качество нового каталога, нынешняя deliverability и
полная экономика остаются непроверенными. Нужны реальные ответы на новый current
вопрос, если пользователь хочет его оценить; отсутствие таких ответов техническое
завершение не блокирует. Следующая партия/monitor не создаются. Cron PAUSED;
merge/mainpush/deploy/productdocs/production не выполнялись. Собственные source/
model процессы и запись явно останавливаются при окончательной передаче.

## Реорганизация модуля и аудит хранения — 11.10.2026

В том же PR194/issue193 рабочая цепочка выделена в [enrichment](../../README.md),
исторические протоколы и тесты сохранены, ссылки продукта скорректированы.
Алгоритмы и рубрика не менялись. [Единая карта](../INDEX.md) и её
[числовой источник](../storage-audit.json) показывают 44 enrichment roots,
216235 файлов / 12521097118 logical bytes, из них Pi cumulative snapshots —
11633708957 bytes. Более широкий census учитывает общий SFR checkout отдельно.
Downloads недоступен; APFS shared extents не измерены.

Read-only replay: 17 прежних index SHA, 2468 mapped файлов четырёх roots;
классификации baseline10 (8 контактов) и live3 (2 контакта) совпали, реальный
human-v3 record и рубрика сохранены байтами. Новый CLI не импортирует Pi
snapshot writer, native сохраняет один events JSONL и полный raw/provenance.
Synthetic fixtures проверяют stream/raw/usage и timeout без реальных transports.
Исторические freezes требуют прежнего checkout, а новый freeze охватывает
фактические файлы пакета.

Архивирование логическое: старые данные не перенесены, не сжаты, не удалены;
освобождено 0 bytes. Новых source/search/profile jobs и ответов человека — 0,
накопленный profile счётчик — 46. При отладке перенесённых mocks native isolation
probe пытался выполнить локальный `codex debug prompt-input`, остановился до
`started.json`/`codex exec`; затем test harness стал блокировать реальные
клиенты и сеть. Это не inference и не новый профильный job. Доказательства
проверок и актуальное независимое ревью/CI с base/head сохраняются в PR.
Метрики актуальности, покрытия и стоимость этим переносом не повышаются.

Независимое ревью переноса выявило разрыв старых mock targets после извлечения
helpers: patch прежнего native имени мог не перехватить фактический runtime.
Compatibility adapters теперь передают подмены/восстановление runtime globals;
проверено разрешение всех 87 прежних patch targets и отдельные native/source/PDF/
atomic-write transport fixtures под offline guard. Повторная проверка относится
к этому исправлению и актуальному committed head; исторические алгоритмы не
менялись. Итоговые доказательства review/CI находятся в PR.
