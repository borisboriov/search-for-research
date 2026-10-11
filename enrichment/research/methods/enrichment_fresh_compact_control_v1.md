# Два свежих контроля выбранного compact

Исполняет последний этап уже закреплённого compact-v1 плана. Новый root создаётся
только после пересчёта и совпадения сохранённых метрик сравнения:6 пригодных
Sol ответов,2 blind Astra jobs, input reduction≥15%, total≥10%, correct не меньше
по атомам/осям и без новых/усиленных high/critical. При failed criterion —0 новых
профилей этого этапа. Старые ответы и ожидаемый победитель в prompts не передаются.

Seed19319420261015: один случайный профиль на вуз по прежнему селектору, затем
Random(seed).sample из12 кандидатов выбирает2. Только выбранные2 входят вsample;
исключаются все ID каждого прежнего sample.json, включая неиспользованные.
SHA действующего9002 каталога, БД, rules/code/artifacts,comparison manifest/metrics
и выбранных профилей закреплены до preflight/source/model calls.

Публичный сбор — тот же Pi CLI GLM-5.3-Flash/high bounded-v4, concurrency1,
4search/8resources including host-onlyrobots, максимум6 model requests, sources
closed before5th/360s/exhaustion, job600s. Затем отдельный nativeSol6.1/high
с той же compact инструкцией и schema только --output-schema. Цитаты и
идентификационные/предметные якоря не сокращаются. Bind/semantic-v3 прежние.
Каждый stage имеет единственную попытку; любой exception сохраняет STOP.
До collector и dependentSol/judge нужен свежий числовой officialquota snapshot,
remainingCodex>15%; после04:30 новыеjobs не начинаются, общий deadline04:49:55.

Один новый Astra/xhigh judge на оба контроля: источник целиком и единственный
ответA, без выдуманногоB. Single-schema/validator требуют ровно все атомы и3 оси
каждого автора, тип/серьёзность ошибок, допустимые refs и basis. Полная semantic-v3,
без инструментов/веба/истории/модельных метаданных/ожидаемого результата.
Это третий judgejob сравнительного цикла (ночной максимум4), не человеческий эталон.

Результаты/raw/receipts остаются неизменными. Native raw/events/prompt и wrapper
сверяются, разрешены только provenance normalization и пустой network_operations.
Packet пересчитывается из проверенных результатов и immutable compare отклоняет
подмену. Judge saved result равенraw; receipt сверяется с исходным.
Итог показывает grade counts/highcritical, usage/time и human_reviewed0.
Два контроля не доказывают точность на каталоге, готовность исследователей,
скорость/цену1000–10000 за60дней или разрешение массового коммерческого применения.
