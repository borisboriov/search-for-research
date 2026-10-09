# Ночной ограниченный конвейер, 09–10.10.2026

Работа в PR [#194](https://github.com/borisboriov/search-for-research/pull/194),
issue #193. [Поручение и жёсткий дедлайн](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6086727260).
Исходная передача: чистый `a4c7d93545f2abaa311df6fe39c8689e60d1346a`,
worktree `/private/tmp/sfr-enrichment100-20261008`, ветка `codex/enrichment100-20261008`.
Основной разработчик requested Sol6.1/high; backend собственной сессии не раскрыт.
Нельзя менять корневой checkout, production, продуктовые документы и паспорт.

## Этап 1: штатный CLI и ограничение сборщика

Первый метод [bounded-v1](../experiments/enrichment_cli_bounded_v1.md),
исправленный [bounded-v2](../experiments/enrichment_cli_bounded_v2.md).
Старые SDK-runner и stopped roots сохраняются. Новое исполнение запускает штатный
`pi --mode json`, без собственного `ModelRuntime`/`streamSimple`/model API вызова.
Session-local расширение использует документированный MCP extension factory
для сериализации/сохранения источников, а native Pi выполняет модель и авторизацию.
Новые физические source calls разрешает обычный host, с точным остатком
4 поисков/8 ресурсов включая robots; источники прекращаются перед шестым
model request/после360с/исчерпании ресурсов, весь job600с, concurrency1.
Потоковые снимки на каждый token-delta не создаются: конечные сообщения,
необходимые события, raw MCP и промежуточные числовые usage учитываются раздельно.
Отказ/таймаут даёт сохранённый partial/unknown и блокирует зависимые задания,
не выдаётся за нормальное завершение модели.

Pi может проглотить ошибку extension handler. Поэтому sticky блокировка
проверяется также перед физическим fetch: ошибка сохранения/контракта/очереди
не разрешает следующий вызов. Некорректные цитаты сохраняются в rejection;
только дословные фрагменты реально прочитанных страниц идут в независимый Sol/high.
Человеческая проверка0. Структурная пригодность и агентская оценка не эталон фактов.

Реальный CLI preflight без inference выполнен в
`/private/tmp/sfr-night-cli-probe-20261009/cli-preflight`:
effective `zai/glm-5.3-flash/high`, ровно два active source tools,
automatic/provider retries0, warming/compaction off, model requests0.
Это проверка конфигурации/доставки расширения, не успешный сбор профиля.
Свежие ID фиксируются отдельным manifest перед первым содержательным запросом;
исключаются все прежние выбранные ID, включая неуспешные и не запущенные.

## Подписки и условия

На старте официальный Codex tool показал used58%, remaining42% недельного
account-wide окна; дельта отдельной сессии не установлена. Reset-credit не используется.
Официальная GLM quota page в доступном in-app browser требует входа: фактическая
квота/тариф/списание неизвестны, login и покупки не выполнялись.

На09.10 [официальная страница Pi](https://docs.z.ai/devpack/tool/pi) описывает
штатный клиент, а [overview](https://docs.z.ai/devpack/overview) включает
research/office и автоматизацию через поддерживаемые инструменты.
[Условия подписки, §4](https://docs.z.ai/legal-agreement/subscription-terms)
ограничивают SDK/general-purpose API и предоставление модельных возможностей
третьим лицам. Поэтому старый embedded runner не запускается. Малый личный
прогон через CLI не доказывает допустимость массового продуктового использования;
до масштаба это отдельное неизвестное, без попыток обхода и обращения в поддержку.

Документарные GLM лимиты/кредитная формула из overview не являются реальным
платежом или измеренной квотой аккаунта. $100–200/месяц относится к GPT/Codex
подписке, плюс GLM; API-стоимость не подставляется вместо этих расходов.

## Проверки и текущие ограничения

Подготовительные `make lint/typecheck/test` прошли:186 unittest и388 pytest,
8 skipped/5 deselected, coverage94,06%. Профильные фикстуры —6 Python/3 Node,
общие транспортные Node17 также проходят. Реальный CLI preflight прошёл без
model request. `docs-check` с действующим `SFR_INDEX_META` прошёл. Strict audit выполнен:
FAIL deps-node/fs-trivy (HIGH sharp/source-map-js), известный #189.
Независимое ревью первого нового head `4c6516fd` — fail, три находки
(IPC stdout, quota stop, общий deadline). Исправления v2 проверяются отдельно.
CI нового head и readonly handoff — обязательные этапы; прежний #189
не исправляется этой работой и критерии не ослабляются.

Первый v1 collector для A5079662185 занял39,996с:3440 total tokens
(2547 input,189 output,704 cached input;132 reasoning входят в output),
1 model request,0 source calls. Native CLI перехватил stdout extension в stderr:
разрешение host не доставилось. Done=false, partial/unknown; Sol не запущен.
Неизменный root `/Users/boris/Experiments/search-for-research/enrichment-night-cli-v1-20261009`
и его STOP сохраняются.

Исправленный v2 использует атомарные durable host-event файлы и учитывает
429 внутри MCP HTTP200 до следующего модельного запроса и до зависимых/новых jobs.
Probe+verifier ограничены единым абсолютным дедлайном с запасом5с.
Реальный CLI preflight в `/private/tmp/sfr-night-cli-ipc-probe-v2-20261009`
прошёл reserve→permission→result→done с локальным transport fixture:
model requests0, физических source calls0, ipc_roundtrip=true.
Это проверка IPC, не сбор данных. V2 закрепляет те же ID/вузы v1 с provenance
повтора, максимум второй collector attempt первого профиля.

Содержательных collector/verifier/judge jobs нового этапа пока1/0/0;
карточек/экономии/точности/масштабируемости не заявляем. После04:30 новые
профили и партии запрещены, до04:50 сохраняются результаты и условия продолжения,
в05:00 работа прекращается независимо от готовности. Следующий запуск требует
нового поручения Бориса после ночной остановки. #193/#47/#103 открыты.
Предложений правок паспорта нет; результат не принят продуктовым потоком.

## Завершённый v2 collector и восстановление v3

Второй collector attempt A5079662185 завершился штатно: done=true,exit0,pending=[];
233,257с,5model requests,2search+2hostrobots+3reader. Raw Pi receipt:
30761 uncached input,9216cached read,11885output (включая8958reasoning),
totalTokens51862. Pi input исключает cached read; cached+input+output дают total,
reasoning отдельно не прибавляется. Это не денежная стоимость/квота.

Postflight host упал KeyError:properties: checker рассчитан на фиксированные
объекты и не поддерживал evidence_pool.additionalProperties. Native verifier
не запускался. V2root/STOP сохраняются. [V3 recovery](../experiments/enrichment_cli_recovery_v1.md)
исправляет проверку dictionary по схеме и копирует исходные данные в новыйroot:
третий collector job не нужен и запрещён. Модельная инструкция остаётсяv2;
новый method/code hash фиксируется отдельно.

Офлайн probe `/private/tmp/sfr-night-recovery-probe-v3-20261009` восстановил
последний assistant, проверил идентификаторы/schema/дословность и Batch.submit:
7атомов,9literal evidence,3rejections. Raw stdout SHA до/после копии одинаков:
`bfc84658789ec033f21ca474145b03e0fe925b5fb2b77f72323b04dd746e36f6`.
Дополнительных inference/source calls0. Это пригодность сохранённого входа,
не независимая фактологическая оценка: первая Sol проверка ещё нужна.

Предзапусковое независимое ревью dbde249ee7585020e1ff5bdae509db4f6a832d85
закрыло прежние3 находки, pass/blocking0; относится к исправлениямv2,
не к итоговой приёмке. Strict audit v2 повторён, FAIL#189; остальные этапыPASS.
SHA-индекс7 прежних roots до исправленного запуска сохранён в v2/prior-roots-before.json;
после всей работы требуется заключительная сверка.

Проверки исправленного postflight: make lint/typecheck/test PASS,190unittest,
388pytest,coverage94,06%; Node21 и docs-check actualmeta PASS.
Дополнительный тест сохраняет прежний строгий запрет лишних полей; dictionary
разрешён только явным typed additionalProperties, его вложенные поля обязательны.

## Первый полный профиль

Рабочий root: `/Users/boris/Experiments/search-for-research/enrichment-night-cli-v3-fixed-20261009`,
manifestSHA `d25523d776b6d667aee04c0c3c771710421422e72972cc736150320606f9ec09`.
Независимый recovery-review head ebf64b482cf4d2f4ad2d7d6f0edeadebac5f69e9:
pass/blocking0; доказана пригодность сохранённого входа, не качество фактов.
Первый independent Sol/high завершён:106,419с,17872input,3770output
(включая1280reasoning),cached0,tool/source calls0. Общий token total21642.

Sol:identity supported,activity supported,current_affiliation insufficient.
7атомов,1полностью поддержанный дополнительный факт (nationality);
положительное покрытие18 исходных полей0. Контакты/история из отдельного PDF
не получили достаточной связи с личностью; сложные смешанные атомы отклонены;
текущий набор не установлен. Завершение конвейера не доказывает качество
обогащения, а unknown не считается отказом человека. Ещё2 профиля идут
последовательно; переход к12 зависит от пригодности этих результатов.

Квота перед следующей партией:Codex used61%/remaining39% accountwide.
GLM фактическая квота/деньги/дельта unknown, reset-credit не используется.

Метод будущего сравнения [compact-v1](../experiments/enrichment_gpt_compact_v1.md)
фиксируется до его model calls:3 использованных сложных saved inputs,
полный baseline vs краткий [verifier](../experiments/enrichment_verifier_compact_v1.md),
источники побайтно одинаковы,2blind Astra/xhigh judges; пороги15%input/10%total,
нет новых high/critical и нет снижения correct. Сравнение только после12
пригодных pipeline results. Сейчас сравнительных jobs0, экономия не заявляется.
Отдельный renderer карточек использует сохранённые оценки, цитаты и даты;
поддержанные дополнительные/исторические факты не смешиваются с положительным
покрытием исходных полей; темы берутся из каталога.

## Остановка четвёртого профиля и ограниченный v4

После трёх completed четвёртый collector A5068285041 завершил шесть физических
model requests ответом «составляю итоговый JSON» без объекта JSON.
180,603 с, input29997 + cacheRead15360 + output7313 = total52670;
reasoning6688 входит в output. Done=true/exit0 не считаются завершением задания:
completion-status=invalid_model_output, dependent Sol и остальные профили остановлены.
Root v3-fixed и STOP сохраняются.

V4 закрывает источники перед пятым запросом и передаёт последним user сообщением
требование полного JSON без вступления или обещания. Предел шесть запросов,
600 с и бюджеты4/8 сохраняются. Новый отдельный root переиспользует первые
три результата без новых calls; только четвёртый допускает вторую исправленную
попытку. Перед расширением v4 нужны три completed на профилях4–6.

Ревью 8b8bde8 выявило один Medium блокер сравнительного runner: производная
validated.json не была связана с первичным raw. До любых сравнительных calls
добавлены сравнение raw→result (у verifier только нормализация provenance),
сверка receipt/events/prompt и seal/содержимое packet→unblinding→проверенные ответы.
Пять offline тестов подтверждают отказ при подмене verdict/grade/receipt/mapping.
Первый compact root имел0 сравнительных calls; он остановлен, нужен новый freeze.
