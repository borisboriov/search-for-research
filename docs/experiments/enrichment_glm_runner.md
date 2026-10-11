# Передача конвейера обогащения и решение по GLM

**Состояние на 11.10.2026:** автономная замена Sol-сессии на GLM не прошла
контроль. GLM допустим только как экспериментальный извлекатель кандидатов с
обязательной независимой проверкой Sol по полной semantic-v3. Готовность
полного гибридного конвейера не доказана; production-ready результат не заявлен.
Заключительный targeted publication/DOI control завершён: **A acquisition fail,
B literal extraction pass, C full independent Sol pass**. Свежий ORCID подтвердил
заранее выбранные title/DOI, первый native query выполнен, но тело целевой статьи
не прочитано. DOI resolver остановлен на robots301 без полного разрешающего файла;
поисковые ссылки не дали точного URL статьи. Единственный новый кандидат —
историческая тема другой ORCID работы2009; контактов0. Решение окончательное для
этой гипотезы: автономный GLM search для каталога не принимаем. Рекомендуемый путь —
ранее успешный Sol-assisted поиск + обычный код + независимая проверка; это рекомендация,
не внедрённый универсальный автономный CLI. GLM остаётся экспериментальным
извлекателем только там, где польза подтверждена. Новых минираундов и batch не назначено.
[Generated final control](../metrics/enrichment_publication_control1_20261011.json).

Предыдущий live3 контроль выполнил 3GLM→3независимых Sol jobs: приняты 2/3 Sol packets,
из них один непустой. Один пакет отклонён по date guard, у второго нет фактов.
Текущая конфигурация не годна для следующего контрольного batch без отдельного
решения по этим отказам; новый запуск не назначен.
Offline policy `live-sol-partial-dates-v1` отделяет atom-local отказ даты от
валидных атомов после полных общих guards. Она не меняет исторический live yield.
Partial остаётся отдельным результатом и не считается полностью принятым пакетом.
На трёх сохранённых live raw Исангулова стала partial:5 validated/1 rejected,
4 usable atoms; Маслов остался identity-only, Ковалёв — accepted3/3.
[Generated offline diff](../metrics/enrichment_live3_partial_offline_20261011.json)
и [Maslov trace](../metrics/enrichment_maslov_trace_offline_20261011.json)
относятся к новой processing policy: model/source/search calls0, cumulative41.
У Маслова DOI/title были видны GLM, но D-Lib URL/body не обнаружены и не читались;
доказанного локального bug нет. Заключительный publication control описан ниже;
исторические результаты не переписаны.
Исправление #197 устранило ложный отказ даты, но не исправляет смысл ответов:
после локальной обработки приняты 5/6 raw, Маслов/GLM остаётся без обязательного
activity.status, чрезмерно уверенные оценки актуальности сохраняются. Принятый
формат и буквальная привязка не означают истинность. Human gold0.

Существующий CLI: `scripts/enrichment_glm_runner.py`. Native Pi 1.1.0 использует
существующую подписку Z.ai, GLM-5.3-Flash/high выбирает запросы, страницы,
буквальные переходы и факты. Python сохраняет HTTP, кэш, robots, источники,
лимиты и проверяет цитаты. Native Sol 6.1/high в live3 проверяет ровно GLM candidates
по всем сохранённым источникам и полной неизменённой semantic-v3; в историческом
offline paired3 две модели независимо извлекали факты. Человеческих оценок и gold нет.

## Частичная обработка сохранённых live ответов

`scripts/enrichment_live_partial.py` выполняет один конечный offline replay трёх
Sol raw из sealed live3. Новый root обязателен; повтор/overwrite запрещён, deadline
≤2 часа. Код сначала сверяет весь старый SHA index и заново строит corpus из
checked saved bodies, затем замораживает scope/code/task/input/raw/receipt SHA.
Новых model/source/search calls нет. Старые источники и архивы остаются по
проверяемым ссылкам; копируются только три набора входов и результатов.

Пример интерфейса (повтор завершённого этапа не разрешён):

```bash
uv run python scripts/enrichment_live_partial.py --root <NEW_PRIVATE_ROOT> \
  --previous <SEALED_LIVE3_ROOT> --scope <SCOPE_MD> --scope-url <PR_COMMENT_URL> \
  --deadline <UTC_ISO_DEADLINE>
```

`process_partial` сохраняет исходный strict schema, четыре task IDs, literal
value/span/ref bindings, semantic-v3 и независимый provenance. Schema, identity
профиля (должна быть supported), source/corpus binding, provenance или любой
profile date guard блокируют все atoms. Это консервативная общая зависимость.
Никакие отсутствующие status/verdict/summary не дополняются. Только отказ
неизменённого atom date guard локален: atom получает rejected/reason и
`usable_coverage=false`; валидные соседние атомы сохраняют классификацию.

Новый wrapper имеет `processing_policy`, `packet_status`, explicit atom states,
profile gates, counts, `fully_validated`, `fully_accepted_nonempty`, untouched
`raw_result` и отдельно normalized provenance. Raw summary помечена как исходная,
не как summary принятой части. Пустой валидный результат — identity_only,
all-invalid — rejected; partial никогда не full success. Live adapter сохраняет
partial только в `partial-verdict.json`, общий/all-invalid отказ в `failure.json`.
Только полностью валидный пакет получает прежний `verdict.json`; старый downstream,
читающий этот файл, не получает partial как успех. Формат partial не имеет legacy
ключа `result`. Усиление общей identity dependency версионировано; это не
доказательство полноты/истинности и не снятие внешнего ORCID конфликта.

## Заключительный targeted publication control

Один отдельно разрешённый Maslov A5054586424 control: anchor заранее выбран
кодом/постановкой из старой публичной ORCID work metadata — A New Face for DSpace,
DOI10.1045/november2007-phillips. Это известный positive control, не случайная
выборка и не автономный выбор лучшей работы моделью. Старые email/articleURL/body
не входят в live task. Scope до calls —
[PR194](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6108525639).

CLI publication-freeze/publication-run использует тот же Pi/SourceHost/Sol.
Свежий ORCID read должен содержать exact title и typed external-id doi внутри
work-summary. Первый native query точно "A New Face for DSpace"
"10.1045/november2007-phillips"; code gate резервирует его до name/public DDG
queries. Остальные≤3queries/hrefs выбирает GLM. После reserved query разрешён
https DOIresolver, построенный из свежего observed DOI: отдельный acquisition
route с обычными robots/redirect/HTTP guards, не exactURL из search.

A — observed metadata→actualquery/resolver→actualURL/redirect→new checked body
с title/DOI/person anchors; B — GLM literal candidates bound by source/fragment
IDs/spans; C — independent Sol проверяет ровно candidates и весь новый corpus.
Unknown/conflicting MEPhI/TexasA&M identity допустима; historical2007 не current,
email не readiness, Human0. Новых jobs≤2 (1GLM+1Sol), cumulative41→≤43;
caps4search/20HTTP/24sourcecalls/12modelrequests/600sGLM/900sSol сохранены.
Deadline2h включает подготовку и передачу; retries/repair/nextbatch0, reserve0.
После единственного контроля — решение о ролиGLM, без нового минираунда.

Фактический итог: A fail — свежих article body/targetURL/redirect нет; сохранены
только ORCID200 и mephi.ru200,36fragments. После exact publication query GLM
попробовал DOI resolver; robots301 вызвал `No full allowing robots` до чтения
статьи. Остальные3query выбрал GLM, все4native запросы исчерпаны. B pass — один
topic candidate из ORCID про Adding OAI-ORE Support to Repository Platforms,
literal fragment/value ID и offsets проверены. Это другая работа2009, не контакт
и не достижение acquisition target. C pass — полный Sol6.1/high проверил ровно
этот кандидат и весь новый корпус; schema/task IDs/provenance/semantic-v3/date
guards прошли. Topic historical2009-05-18; identity supported по совпадению
ORCID, affiliation/activity insufficient, activity status unknown. MEPhI/TexasA&M
ambiguity и принадлежность отсутствующего контакта не разрешены; Human0.

Новых jobs2/cumulative43: GLM8requests/73273tokens (21120cacheRead внутри total),
Sol43921tokens (cache0; reasoning291 внутри output),4search/8sourcecalls/4HTTP.
Wall profile jobs308.787s; USD/списание unknown. Accountwide weekly остаток82→81%
включает разработку/ревью/другую активность и не даёт стоимости этого профиля.
Это один known targeted control, не coverage/economy/готовность1000профилей.
Execution terminal STOP, cron PAUSED; fallback или новый batch не запускались.

## Что делал baseline

В flexible10 обычный код загружал ORCID/HTML/PDF, соблюдал ограничения,
извлекал текст, выполнял публичный Math-Net decoder и связывал цитаты с bytes.
Главная сессия Sol выбирала 23 логических запроса через web.run, страницы,
переходы и контекст; одноразовые драйверы сохраняли выбранные планы.
459511 токенов и 645.630 секунды относятся только к десяти проверкам native Sol.
Токены/время главной сессии и внутренняя физическая стоимость web.run неизвестны.
Это не измеренная стоимость автономного сбора baseline.

## Историческая live-команда и доказательства

Следующая команда существует в CLI, но успешный полный автономный проход
GLM→независимый Sol для frozen10 **не подтверждён**. Это описание исторического
пути, не разрешение нового запуска; прежние roots имеют terminal STOP.

После `uv sync --locked --all-packages --all-groups`:

```sh
UV_NO_SYNC=1 .venv/bin/python scripts/enrichment_glm_runner.py run \
  --root /absolute/new-private-root \
  --baseline /absolute/sealed-flexible10-root \
  --baseline-pdf-module-path /absolute/original-python-site-packages \
  --scope /absolute/frozen-scope.md \
  --scope-url https://github.com/borisboriov/search-for-research/pull/194 \
  --remaining-percent ACTUAL_OFFICIAL_PERCENT
```

Root должен быть новым. Команда проверяет baseline seal, копирует sample,
политику ORCID, версии кода и scope, проводит Pi preflight без inference,
затем обрабатывает фиксированные группы 2+4+4: один GLM job на человека и
один полный Sol job на группу. Начальные два — контроль инструментальной
цепочки. Ошибка группы останавливает продолжение; повторных jobs нет.
Итог, включая частичный результат, сохраняется с STOP. Команды отдельных
этапов доступны для диагностики; они запрещают перезапись и повтор jobs.

`live` не читает baseline URL, факты и оценки. GLM получает frozen profile и
известный ORCID record. Native Z.ai search регистрирует только actual title/link
rows; сниппеты не доказательства. Дополнительный обычный публичный поиск —
[DuckDuckGo HTML](https://duckduckgo.com/duckduckgo-help-pages/features/non-javascript),
тот же общий лимит запросов. Search HTML хранится только как discovery.
Переходы разрешены только по наблюдённым href/URL. Отказы robots, 403/429,
CAPTCHA/challenge блокируют источник; обходов, логина и платных API нет.
`replay` использует только тела источников frozen baseline и не имеет live
fallback: он проверяет интерпретацию материалов, а не обнаружение источников.
`run --mode replay` также вызывает GLM и Sol; это не повторная обработка raw.

Новые PDF извлекаются locked pypdf 6.19.0. Чтобы не переписывать старые PDF
цитаты/offsets, воспроизведение baseline использует снимок исходного pypdf
6.10.0 исключительно для четырёх allowlisted body SHA. Все файлы снимка
проверяются; новый PDF этим парсером обрабатывать запрещено. Изолированный
процесс имеет timeout и не пишет bytecode. В lock и live остаётся исправленная
версия; исключений аудита нет. Для исходного сравнения нужен доступный sealed
baseline; повторный live-сбор по определению может встретить изменившиеся сайты.

## Замороженные пределы и сравнение

На старт дня уже 17 профильных jobs: новый запуск максимум 10 GLM + 3 Sol,
итого ≤30. Резерв Codex 0 разрешён пользователем; actual refusal останавливает
новые jobs. Astra 0, покупок/reset нет. До первого source/model вызова scope
и manifest фиксируют: 90 минут, GLM ≤12 model requests/600 секунд, 24 локальных
source tool calls на человека; HTTP ≤200 всего/20 на человека; search ≤40/4,
последовательно, ≤1 rps/host, ≤6 href hops, ≤5 redirects, HTML/JSON ≤2 MiB,
PDF ≤8 MiB. Retry 0; одинаковый запрос к тому же поиску запрещён.

Sol получает индивидуальные входы со своими SHA, schema и source refs;
перекрывающиеся цитаты объединены без удаления текста. Старых verdicts нет.
Групповой JSON ≤600000 UTF-8 bytes; целиком не поместившийся человек пропускается
с причиной. Полная рубрика не сокращается. Проверенные стороны и объяснение
расхождений сохраняются отдельно; baseline не считается gold.

Малый тест считается без регрессии, только если проверены все десять пар,
сохранены полезные контакты, личность и подтверждённая аффилиация, нет
непринятых GLM атомов и необъяснённых изменений даты/применимости контакта.
Различия, в том числе изменение самого baseline при повторной оценке, видны
в private metrics и pair explanations. Пустой/непроверенный результат не PASS: GLM identity должен быть supported по сохранённым
доказательствам. Контакты/аффилиация могут оставаться unknown, если полезные
baseline факты не потеряны; равенство двух пустых unknown входов не достаточно.

`metrics.json` содержит private контакты и source URLs; его не переносить в git.
`public-metrics.json` — детерминированная числовая проекция, пригодная для отчёта;
`comparison-table.md` — таблица тех же результатов. GLM input в Pi уже uncached;
cacheRead/cacheWrite и reasoning (если раскрыт, входит в output) учитываются
отдельно. У Sol input включает cached: uncached=input−cached. Shared Sol receipt
суммируется один раз за группу. Сравнение старого verifier ограничено фактически
проверенными людьми; новый verifier проверяет две стороны и использует grouping.
Расходы сбора, проверки и разработки не смешиваются. Для partial-прогона числовые суммы — наблюдённый нижний предел; полные
токены/wall неизвестны (`null`), reserved/started/completed jobs считаются
отдельно. После внешнего прерывания recovery receipt с SHA исходных событий
дополняет отдельный summary: `summarize --summary-suffix=-reconciled`; исходный
summary не перезаписывается. Никаких новых источников или моделей этот этап
не запускает. Денежная цена подписки,
главная сессия baseline и overhead разработки/ревью неизвестны; API-доллары,
экономия общего цикла и масштабирование на 1000/10000 не заявляются.


## Результат единственного запуска 2026-10-10

Frozen f5454ea остановлен по High finding независимого ревью: Pi может
перехватить hook exception. Сохранены 17 model request configs/HTTP observations,
GLM jobs2, Sol0, день19/30. Первое извлечение отвергнуто дословным binder,
второй job прерван; сравнительных пар0. Исправленная версия имеет terminal latch
на sync/async callback boundaries, физический model fetch cap, MCP semantic
refusal STOP, запрет snippet URLs и явные eligibility/partial cost состояния.
Девять Python и две JS offline проверки проходят; новый live/replay inference
после просмотра исходов не выполнялся. Полное неухудшение/экономия не доказаны;
исправленная цепочка требует отдельного ограниченного эксперимента по новой
постановке. См. [фактический отчёт](../reports/enrichment_night_20261009.md).


## Продолжение на оставшихся восьми

По отдельному поручению в PR #194 разрешён новый live-root с
`--continuation-from /absolute/sealed-stopped-runner-root`. CLI проверяет seal
предшественника, тот же frozen10, две уже потраченные collect-попытки и счётчик
19. Первые два ID исключены до reservation; scheduled IDs — остальные восемь
в исходном порядке. Счётчик цикла продолжается 19→≤30 при смене даты.
Максимум восемь GLM и три Sol, deadline нового freeze — 150 минут; прежние
STOP, тела, метрики и deadline не меняются. Инструкция GLM, output schema,
строгая привязка цитат, source limits и semantic-v3 сохранены.

Группы заранее фиксированы 1+3+4. Первый непустой source-bound пакет
проверяется сразу до дальнейшего сбора; продолжение требует фактически оценённой
пары. Если полная первая пара не помещается или проверка не завершена, STOP partial
без расходования остатка на непроверенный сбор. Если он появляется внутри более поздней
группы, эта группа проверяется один раз с уже пригодными пакетами; ещё не
собранные её профили остаются непроверенными. Остальные группы проверяются
после своего сбора. Пустые пакеты не расходуют Sol job. Непригодный отдельный
GLM результат не останавливает других людей; общий STOP/отказ провайдера,
deadline или отказ цепочки независимой проверки завершают partial без повторов.

Это оставшиеся восемь devset-профилей с известным агентским baseline и human0,
а не единый чистый новый10-run. `all_paired_profiles_nonregression` сохраняет
критерий всех десяти; отдельный `all_scheduled_profiles_nonregression` относится
только к полностью проверенному текущему расписанию. Код и план замораживаются
после необходимых проверок и независимого ревью до live.


### Фактическое продолжение 11.10.2026 (Москва)

Единственный live-freeze4e85631 выполнил2 из8 scheduledGLM jobs, Sol0/пар0,
цикл19→21/30. Первый packet отклонён literal binder; второй job прерван
необработанной unknown source encoding windows-874. Остальные6 не запускались,
старые2 не повторялись; STOP сохранён. Сумма222035 токенов — наблюдённый нижний
предел, exact full tokens/wall неизвестны. Неподдерживаемая кодировка затем
исправлена offline как локальный source ValueError без guessed text; нового
live-прохода нет. Полное качество/расходы не установлены. См. отдельный раздел
[отчёта](../reports/enrichment_night_20261009.md) и его generated public JSON.

### Последний разрешённый этап: remaining6

Новая постановка в PR #194 разрешает ещё один отдельный live-root после
offline исправления кодировки. `--continuation-from` указывает на sealed
remaining8 root: проверяются обе предыдущие SHA-печати, frozen10, ровно две
его collect-попытки, начальный счётчик19 и итог21. Четыре уже начатых ID
исключаются до reservation; новые шесть — исходные позиции4–9.

Новый конечный deadline150 минут; максимум6 GLM +3 Sol, общий цикл21→≤30.
Группы2+2+2 фиксируются до calls и проверяются последовательно после сбора
каждой группы, до следующей. Только непустые source-bound inputs проходят
полную парную semantic-v3; целый input сверх прежнего cap пропускается с
причиной, рубрика/цитаты не обрезаются. Early first-pair gate remaining8
к этому отдельно разрешённому расписанию не применяется. Непригодное
извлечение не расходует Sol и не останавливает следующего человека;
неизвестная кодировка — локальный source error без угадывания текста.
При новом общем системном блокере, quota refusal или deadline — итоговый
STOP, без новой серии починок и повторных model jobs. Это третья отдельная
попытка на том же devset, прежние2+2 учитываются раздельно, human/gold0.


Последний frozen40e560d завершил6/6 collect без общего runtime сбоя;
source-bound1/6, paired1/6. Binder отверг4 недословные цитаты и1 URL без
savedbody. В одной паре потерян historical контакт2007; identity сохранена,
current affiliation/readiness не подтверждены. GLM62requests/750040tokens,
Sol1/30842tokens, cycle28/30. Эта версия метода ненадёжна, nonregression
не выполнен; остальные5 без семантической оценки, human/gold0, экономия
полного цикла неизвестна. Данные и ограничения — в отдельном разделе
[отчёта](../reports/enrichment_night_20261009.md) и generated remaining6 JSON.

## OFFLINE fragment-ID paired3: отдельный этап после 28/30

Постановка [PR194](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6105694857)
разрешает новый конечный этап, не обнуление старого счётчика. До inference
зафиксирован порядок: A5089458364 (Исангулова, прежняя недословная цитата),
A5054586424 (Maslov, пропущенный historical контакт), A5054791318 (Kovalev,
сложная атрибуция чужих/общих контактов). Human0, прежние агентские результаты
использованы только для объяснения выбора и не входят в модельный вход.

Обычный код объединяет все сохранённые source records baseline flexible10 и
remaining6 для каждого человека, включая все уже сохранённые `rendered-sources`,
устраняя дубли по URL/bodySHA/textSHA и сортируя
по той же тройке. `checked_source` проверяет bytes/деривацию; исторические PDF
воспроизводятся прежним checksum-allowlisted parser. Каждый static text целиком
разбит на фрагменты1800 символов с шагом1500; CRLF сохраняется. Старое проверенное
Math-Net rendering воспроизводится только из сохранённых parent/decoder bytes;
raw и rendered representations различаются во входе, dependency receipts копируются. Всем фрагментам
и всем буквальным email matches присвоены ID с author/source/offset. Контекст
не выбирается по адресам или будущим ответам. Полный source Maslov с контактом2007
добавлен явно из baseline обеим моделям: в новых acquired remaining6 телах
этого факта нет. Это проверка анализа общего корпуса, а не нового retrieval.

Модели получают одинаковые task/corpus/order/schema и общую инструкцию плюс
полную неизменённую semantic-v3. Выбирают value_id и evidence_refs; код буквально
восстанавливает цитату/значение по offsets. Каждый выбранный атом получает все
семантические оценки, identity/date/affiliation/activity/summary обязательны.
Несуществующие/чужие ID, неверные spans/SHA, отсутствие собственного anchor,
перенос чужих evidence и неопределённая дата с придуманным годом отвергаются.
Год установленной даты должен буквально присутствовать в выбранном evidence
(либо указанном metadata для source_metadata). Это проверка происхождения числа,
не доказательство отношения даты к человеку или актуальности факта.
Email — буквальный кандидат, его принадлежность код не определяет. Личные контакты
не принимаются только по совпадению текста, без supported identity/object relation.

Это интегрированный выбор и семантическая атрибуция в одном job на модель и
человека, с полной рубрикой; самооценка не выдана за независимую вторую проверку
своего извлечения. Независимость сравнения — разные контексты GLM и Sol.
Совпадение моделей не human gold; расхождения и пропуски сохраняются.

```sh
UV_NO_SYNC=1 .venv/bin/python scripts/enrichment_glm_runner.py offline-freeze \
  --root /absolute/new-offline-root \
  --baseline /absolute/sealed-flexible10-root \
  --continuation-from /absolute/sealed-remaining6-root \
  --scope /absolute/scope.md --scope-url https://github.com/borisboriov/search-for-research/pull/194 \
  --deadline FIXED_ISO_DEADLINE --remaining-percent ACTUAL_OFFICIAL_PERCENT
UV_NO_SYNC=1 .venv/bin/python scripts/enrichment_glm_runner.py offline-run \
  --root /absolute/frozen-offline-root --remaining-percent ACTUAL_OFFICIAL_PERCENT
```

Freeze требует чистый коммит, две прежние SHA-печати и ту же frozen10;
сохраняет весь corpus, provenance/source snapshots, code/prompt/schema SHA.
Максимум6 новых profile jobs (3GLM+3Sol), cumulative28→≤34, старый цикл28/30
сохраняется. Конечный deadline≤3часа, ≤600секунд на job, без повторов и Astra.
Общий prompt≤1000000 UTF-8 bytes; целый корпус сверх cap вызывает отказ без
скрытого усечения. Pi требует ровно один tool-less model request и physical cap1;
Sol — существующий изолированный native runner. Поиск и source вызовы0.
Ошибка, фактический отказ квоты или deadline сохраняют partial/STOP, последующие
jobs запрещены; offline исправление не разрешает дополнительный model job.
Расходы разработки/ревью отделены от шести профильных попыток; деньги/debit,
не раскрытые runtime, остаются unknown. Экономия полного коллектора не измеряется.

### Фактический OFFLINE этап и исправление сериализации

Freeze6a0f5e8 от11.10.2026 остановлен после одной незавершённой GLM попытки:
Sol0, completed0, pairs0, stage1/6, cumulative29; прежний cycle28/30 неизменен.
`encoded(sort_keys=True)` пересортировал вложенные task/corpus/schema keys;
actual Pi prompt SHA отличается от общего frozen SHA при равных JSON-данных.
Автор прервал проход; terminal STOP запрещает остальные пять jobs и повтор.
Семантического результата нет: качество GLM и буквальное восстановление новых
выбранных атомов не оценены. Pending SDK usage0 не является фактическим расходом;
tokens/cache/debit/cost неизвестны. Один interrupted attempt занял207.085s.

Offline исправление сохраняет вложенный порядок request только для этого метода.
Ожидаемый общий prompt SHA передаётся из manifest; Python проверяет его перед
запуском, JS сверяет свою фактическую проекцию до model request, importer/driver
также сверяют receipts. Остальные методы сохраняют прежнюю сериализацию.
Тест воспроизводит сортировку вложенных fragments/schema keys и её отказ;
offline proof через mocked `Popen` и реальный JS helper подтвердил все три
frozen prompt SHA без model/source calls. Нового freeze/inference после STOP нет.
Подробности, ограничения и generated JSON — в следующем разделе
[отчёта](../reports/enrichment_night_20261009.md#offline-fragment-id-paired3-11102026-partialstop).

### Отдельно разрешённый повтор после merge main

Повторная постановка PR194 разрешает обычный merge актуального main с fix189,
затем новый root/freeze на тех же трёх corpus/task/instruction bytes и semantic-v3.
`offline-freeze --offline-repeat-from` указывает на прежний terminal partial1:
проверяются его полный SHA-index5939d28e…, STOP, cases и cumulative29.
Все старые капы/факты сохраняются: cycle28/30, partial1/6, новыйstage≤6,
cumulative29→≤35. Дедлайн повторного этапа09:07:02UTC11.10.2026, job≤600s;
search/source/live/newpeople/Astra0, без повторов сверх нового cap.

До calls actual `run_pi` serializer с mocked process и реальный JS helper
должны воспроизвести SHA/bytes всех трёх frozen prompts. Python/JS guard остаётся
в реальном пути до отправки. Freeze дополнительно отвергает любое отличие
corpus/task/instruction/prompt metadata от прежнего immutable root.

Отдельный невалидный semantic output сохраняется как failure с raw SHA/receipt;
прочие jobs продолжаются без повтора. Неполный Pi reply допускает продолжение
только при доказанных actual common prompt/instruction SHA, approved SDK config,
empty tools и отсутствии provider access/quota STOP. Общая ошибка входа/метода,
неподтверждённый runtime, native отказ, quota/deadline/operator interrupt
останавливают этап. Каждый outcome сохраняется; normalized result требуется
для пригодной пары. Unknown usage не0, sourcebound неsemanticcorrect, human0.
Крон остаётся PAUSED; новое сопровождение/следующий эксперимент не назначены.

### Offline date policy для #197

`fragment-date-v2-orcid-employment-ms` применяется только к обработке результата,
не меняет prompt/schema/semantic-v3 и не разрешает inference. Для
`current_affiliation.date_basis=source_metadata` поддержан узкий типизированный
случай ORCID `employment-summary.created-date/last-modified-date.value`:
целое 13-значное epoch milliseconds преобразуется в UTC детерминированно.
Source kind/endpoint и ORCID identifier должны совпадать с фиксированным
профилем; весь saved JSON восстанавливается из согласованных fragments с
проверкой textSHA, длины и duplicate keys.

Конкретный employment определяется до сравнения дат: cited spans должны
покрывать его put-code, path и organization.name. Требуется ровно один такой
объект. Два cited employment, чужой object/path, uncited date field, timestamp
коллекции/works и произвольные числа не принимаются. Ровно одно из двух
типизированных полей должно дать указанную календарную дату с её точностью.
Epoch seconds, строки/boolean и metadata update после saved checked_at
отвергаются; checked_at служит только верхней границей, никогда date evidence.
Другие виды source_metadata пока unsupported, без fallback к буквальному году.
Обычный literal-year guard для content дат сохранён.

Normalized wrapper получает policy и metadata binding (sourceID, JSON path,
object path, integer milliseconds, UTC, cited refs); исходный model result,
semantic classifications и даты не дополняются/не исправляются. Это проверка
формата происхождения, а не подтверждение нынешней affiliation/activity,
принадлежности контакта или готовности руководить. Для разрешённой повторной
обработки шести saved raw используются новый root/версия, точные input SHA и
старый cumulative35; raw/STOP/seals/исторические normalized и metrics неизменны.
Новых model/source/search calls0; пропущенный activity.status не восстанавливается.

## Практическая передача существующих путей

| Путь | Что подтверждено | Роли и ограничение |
|---|---|---|
| Flexible10 | Сохранённые загрузки, 10 входов и native Sol checks | Обычный код связывает тела/деривации/цитаты; техническая Sol-сессия выбирала 23 web.run queries, страницы и планы. Этот успех не доказывает автономность GLM либо универсальную CLI-команду поиска. |
| GLM live | Реальные bounded attempts и partial/STOP | GLM выбирает источники/кандидаты; Python ограничивает доступ и проверяет literal binding; Sol независимо проверяет отдельные стороны. Полный контроль не пройден; remaining6 дал только 1/6 пригодных пар. |
| Offline3 | Шесть model jobs на трёх одинаковых сохранённых корпусах | GLM и Sol независимо анализировали корпус, поиска0. Это проверка анализа, не discovery; каждый ответ сам оценивает свой выбор, независимый второй verifier для GLM здесь не запускался. |
| Raw replay после #197 | Локальная обработка прежних шести ответов: 5 accepted, 1 rejected | Только `hydrate`/semantic-v3/date guard; новых моделей, поиска и HTTP нет. Две пригодные пары не доказывают semantic correctness или качество полного поиска. |
| Человек | Существуют локальные карточки и importer фактических ответов | Human records не заполнялись; human0 нельзя заменить совпадением моделей или проверкой технического агента. |

### Команды и границы воспроизводимости

Из корня checkout нужны Python≥3.12 и зависимости `uv.lock`/`pyproject.toml`;
установка — `uv sync --locked --all-packages --all-groups` (при передаче только
проверена по конфигурации, повторно не выполнялась). Ниже реально выполнены
`--help`, затем read-only raw replay. Help завершается до dispatch:

```sh
.venv/bin/python scripts/enrichment_glm_runner.py --help
.venv/bin/python scripts/enrichment_human.py packet --help
.venv/bin/python scripts/enrichment_pair_human.py --root ./human-work generate --help
```

`freeze` и `offline-freeze` — подготовка новых roots, snapshot/проверка seals,
corpus/schema/prompt и ограничений; `preflight` — проверка Pi без inference.
Здесь они проверены по entrypoints, не исполнялись. `run`, `collect`, `verify`,
`offline-run` и `run --mode replay` вызывают модели. `summarize` пересчитывает
агрегаты из сохранённых результатов/receipts без моделей, **пишет** immutable
metrics/public-metrics (суффикс `-reconciled` для разрешённого нового снимка);
это не универсальный read-only replay и не команда fragment postprocessing.
Terminal STOP старого root не снимается; подготовка нового запуска требует
отдельного конечного поручения, нового root и scope/deadline/quota, не смены
старых исторических лимитов. Ни одна из этих live-команд в этой передаче не
запускалась. Исторический `sfr197-reprocess.py` содержит фиксированные root/head
и является доказательством этапа, а не переносимым общим CLI.

Для **повторного чтения и проверки шести уже полученных raw** используется
существующий Python entrypoint `enrichment_fragments.hydrate`, без нового runner.
Указать расположение копии sealed `enrichment-orcid-date-offline6-20261011` в
`SFR_SAVED_ROOT`; имя домашней папки и исходный абсолютный путь не являются
контрактом. Из корня checkout выполнить пример ниже через
`.venv/bin/python - <<'PY' … PY`. Пример проверяет SHA четырёх inputs каждого
ответа, внутреннюю связь task/corpus и неизменность raw; выводит только статусы.
Он не проверяет весь старый архив или его внешние источники. Результат на коде
#197: Isangulova/GLM и все Sol accepted, Kovalev/GLM accepted, Maslov/GLM rejected
с `Лишние или отсутствующие поля JSON schema`; отсутствие activity.status
установлено сравнением сохранённого raw/schema, не дополнено при обработке.

```python
import copy, hashlib, json, os, socket, sys
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, "scripts")
import enrichment_fragments as fragments
from enrichment_native import normalized_provenance

root = Path(os.environ["SFR_SAVED_ROOT"]).resolve()
read = lambda p: json.loads(p.read_bytes())
manifest = read(root / "manifest.json")
rows = []
with (
    patch.object(fragments, "run_pi", side_effect=AssertionError("model forbidden")),
    patch.object(fragments, "execute", side_effect=AssertionError("model forbidden")),
    patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")),
):
    for entry in manifest["inputs"]:
        saved = {}
        for kind in ("task", "corpus", "raw", "receipt"):
            info = entry["files"][kind]
            path = (root / info["snapshot"]).resolve()
            assert path.is_relative_to(root)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == info["sha256"]
            saved[kind] = read(path)
        assert saved["task"]["corpus"] == saved["corpus"]
        assert saved["task"]["input_sha256"] == entry["files"]["corpus"]["sha256"]
        original = copy.deepcopy(saved["raw"])
        try:
            fragments.hydrate(
                saved["task"],
                saved["raw"],
                normalized_provenance(saved["receipt"], "fragment_analysis"),
            )
            status, reason = "accepted", None
        except ValueError as error:
            status, reason = "rejected", str(error)
        assert saved["raw"] == original
        rows.append(
            {
                "author_id": entry["author_id"],
                "model": entry["model"],
                "status": status,
                "reason": reason,
            }
        )
print(json.dumps(rows, ensure_ascii=False, indent=2))
```

### Файлы для передачи и человеческая проверка

Для указанного raw replay достаточно нового root #197: `manifest.json`,
`inputs/<author_id>-<model>/{task,corpus,raw,receipt}.json` (24 файла), кода
на зафиксированном head и lock. В `manifest.inputs[].files` находятся относительные
snapshot paths и SHA. `normalized/` (5 файлов), `failures/` (1), `public-metrics.json`
и `transfer-SHA-index-5a436c6.json` сохраняют результат/проверяемый снимок #197.
SHA этого индекса: `a5543ca1336dfa7adcd8ca43b3b4844cc13c460c46a288d61fefa5cac4ee5f62`.
Для воспроизведения именно исходного inference нужны также repeat3
`tasks/`, `corpora/`, `instruction.txt`, `runs/…/request.json`, raw/receipts и
manifest common-prompt SHA; это отдельный разрешаемый запуск, не текущий replay.
SHA его `transfer-SHA-index-ccde0f9.json`:
`a246a34dfae999d0b150df8506586eb590379654653c720a72a433cbc0b0bd94`.
Старые roots доступны по ссылкам и SHA в `prior-seals-final-recheck.json` нового
root #197; для этой docs-передачи их содержимое рекурсивно не копируется.
Сами старые архивы, raw, metrics и STOP сохраняются.

Модельные инструкции: collector `INSTRUCTION`/schema в
`scripts/enrichment_glm_runner.py`; offline3 `instruction.txt` и `output_schema`
в `scripts/enrichment_fragments.py`; полная rubric
[semantic-v3](enrichment_verifier_v3.md). Requested configs —
`HIGH_CONFIGS` в `scripts/enrichment_pi_pilot.py`: GLM-5.3-Flash/high и
native gpt-6.1-sol/high; фактические backend model/effort runtime не раскрыл.
Для Pi нужны Node, установленный Pi1.1.0 и его SDK/MCP configuration;
`scripts/enrichment_pi_runner.mjs` использует release текущего пользователя,
CLI extension пока привязан к layout Pi1.1.0. Native runner требует совместимый
`codex exec` и собственный разрешённый доступ оператора. Python lock не ставит
и не закрепляет эти внешние runtimes. Credentials/config аккаунта не копируются
в пакет; перенос live runtime на другую машину не подтверждён. Live использует
pypdf6.19.0; только старые allowlisted PDF требуют sealed snapshot pypdf6.10.0.
Read-only raw replay не нуждается в Pi/Codex login, HTTP либо PDF parser snapshot.

Имеющиеся незаполненные парные карточки — в root `enrichment-pi12-20261009`,
`paired-human/packets/pi12-01`…`pi12-04/{cards.html,manifest.json}`; mapping хранится
отдельно в `paired-human/unblinding/`. Это прежний Pi12, не новые offline3 пары.
Можно открыть сохранённый `cards.html` локально; экспорт ответов сохраняет
`actual_human_attestation`, имя, время и длительность. Импорт в **новую рабочую
папку** оставляет sealed пакет и модельные ответы неизменными:

```sh
.venv/bin/python scripts/enrichment_pair_human.py --root ./human-work import-answers \
  --manifest ./saved-packet/manifest.json --answers ./actual-human-answers.json
.venv/bin/python scripts/enrichment_human.py packet --root ./human-work \
  --entries ./human-entries.json --packet-id control-01
.venv/bin/python scripts/enrichment_human.py import --root ./human-work \
  --manifest ./human-work/human-v3/packets/control-01/manifest.json \
  --answers ./actual-human-answers.json --record-id control-01
```

CLI формы подтверждены help/code, новые карточки/ответы в этой передаче не
создавались и не импортировались. Single entries: `input_path`, `assessment_path`,
`stratum` (`random/targeted/corrected/pilot`), `selection_reason`; v3 wrapper
требует `result`, `input_sha256`, `classifications`. Paired generate принимает
`input_path`, `result_paths={pi,native}`, `selection_reason` и `--blind-seed`;
обе стороны должны оценивать **одинаковые items одного input**. Fragment wrapper
`{input,result,derived}` непосредственно этим CLI не подходит, выбор items двух
моделей различается: нельзя выдать готовые offline3 human cards за существующий
артефакт. Нужна явно описанная проекция без изменения raw и смешивания items либо
ручная проверка сохранённых evidence. Локальные entries/mapping с путями требуют
переуказания мест хранения при переносе; сохранённый manifest не редактируется.
Человек оценивает принадлежность, даты/применимость и нынешнюю аффилиацию отдельно;
публикации и общие контакты не подтверждают готовность руководить.

### Размеры, расход и оставшиеся условия

Сохранённые файлы #197 и полные общие prompts repeat3 (UTF-8 bytes,
не число токенов); task/corpus идентичны для двух моделей:

| Corpus | Sources / fragments / literal email values | Corpus / task bytes | Raw GLM / Sol bytes | Prompt bytes |
|---|---|---:|---:|---:|
| A5089458364 | 4 / 54 / 3 | 136348 / 138104 | 13573 / 11529 | 141908 |
| A5054586424 | 4 / 37 / 5 | 97910 / 99286 | 12757 / 7452 | 103157 |
| A5054791318 | 10 / 188 / 26 | 471497 / 476911 | 17659 / 17095 | 478797 |

Размеры файлов проверены чтением metadata сохранённых inputs #197; corpus/prompt
показатели и usage взяты из [generated repeat3 metrics](../metrics/enrichment_fragment_repeat3_20261011.json).
У группового live JSON cap600000bytes, у общего offline prompt cap1000000bytes;
они не являются token/context limits провайдеров. Полный человек/корпус сверх
cap отвергается с причиной, не скрыто усечён. За три прошлых jobs каждой модели:
GLM280773tokens/1205.914s, Sol263699tokens/283.222s. Pi input/output/cache buckets
раздельны, Sol cached input — подмножество input, reasoning — подмножество output;
его нельзя прибавлять вторично. Оба cache0; GLM3 physical requests наблюдались,
Sol3 logical CLI jobs, hidden physical requests неизвестны. Новая обработка
не добавляет этот расход снова. Деньги/actual subscription debit неизвестны;
SDK catalog cost не billing, расход разработки/review не измерен. Экономия
full collector, 1000/10000 profiles и human accuracy не установлены.

| Реальный пробел | Минимальное условие следующего честного e2e контроля |
|---|---|
| Неполный GLM output; semantic overclaims текущего состояния | Неполный ответ остаётся failure без придуманного status. Независимый Sol проверяет GLM candidates по полной rubric и сохраняет расхождения/unknown; дата metadata не повышает факт до current. |
| Разные механизмы поиска | Зафиксировать доступные GLM native search/DDG tools и возможности Sol web.run: одинаковый текст запроса не делает retrieval одинаковым. Проверять реальные найденные bodies, пропуски и отказы, а не snippets. |
| Live3 выполнен, принят один непустой пакет | Три live collector packets переданы трём независимым Sol по полным sources; date guard отверг Исангулову, Маслов identity-only без фактов, Ковалёв 3atoms. Это не устойчивый полный проход и не human quality; следующий batch требует отдельного решения по этим ограничениям. |
| Нет человеческого эталона и переносимого запуска поиска flexible10 | Явно определить human пакет/контракт для сравниваемых items, получить реальные ответы отдельно от моделей; описать и подтвердить runtime/dependencies на целевой машине. Пока качество и переносимость поиска остаются непроверенными. |
| Неизвестная стоимость полного процесса | Разделить сбор, независимую проверку и development/review; сохранять раскрытый usage и неизвестные debit/physical costs. Без измерений не утверждать денежную экономию. |

Эти условия не назначают новый эксперимент и не требуют серии дополнительных
мини-раундов. Итог передачи — воспроизводимый read-only postprocessing и
честные границы существующих инструментов. Cron PAUSED, профильные model/source/
search calls этого этапа0; после передачи запись и собственные процессы STOP.


## Разрешённый live3 → независимый Sol контроль

Постановка [PR194](https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6107652850)
фиксирует только A5089458364/A5054586424/A5054791318: известные development случаи,
не случайный контроль. До freeze offline проверяется минимальный adapter:
`SourceHost` выдаёт стабильные source/fragment/value IDs, GLM выбирает кандидаты,
код восстанавливает literal value/quote; raw/rendered representations сохраняются
отдельно. Discovery/search snippets в корпус не входят. У GLM bounded text views,
их усечение явно обозначено; Sol получает все fragments всех реально сохранённых
live bodies с URL/body/text/source-record SHA, включая невыбранный GLM контекст.
GLM identity/current_affiliation refs — evidence candidates, не verdicts.

Новый `live3-freeze` принимает только каталоговые seeds исходного sample с
точными provenance/SHA и фиксированными3ID, policy/scope/deadline; никаких старых
email/pageURL/вердиктов/тел в GLM task. `live3-run` делает до3collector jobs и
до3индивидуальных Sol6.1/high: оцениваются ровно GLM items, не ещё одно
самостоятельное извлечение. Identity-only пакет проверяется; если нет ни items,
ни identity refs — Sol skipped. Schema failure/raw остаются неизменными,
обязательный status не дополняется. Код повторно проверяет полный saved corpus,
неизменённую semantic-v3 и общий date provenance guard #197; metadata не currentfact.
Ошибка одного profile output не повторяется и не отменяет остальные случаи;
общая method/runtime/quota/deadline ошибка заканчивает этап с partial/STOP.

До live выбран конечный budget: stage≤6jobs/cumulative35→≤41,
GLM≤12physical requests/600s и24sourcecalls/person, shared search≤4/person/12total,
HTTP≤20/person/60total (robots/redirects включены), host≤1rps, redirects≤5,
hrefdepth≤6, HTML/JSON≤2MiB, PDF≤8MiB; Sol≤900s/person и полный prompt≤1000000UTF8bytes.
Сверх prompt cap весь профиль skipped, без скрытого удаления источников/рубрики.
Это прежние individual caps successful runtime remaining6 (6jobs/62requests),
умноженные на3для общих HTTP/search; они не доказывают качество. Внутри run caps
не повышаются. Deadline всего этапа12:34:36UTC11.10.2026 (3h от first-tool clock),
reserve0 разрешён; retries/repair/Astra/paidAPI/reset/accountchanges0.

```sh
.venv/bin/python scripts/enrichment_glm_runner.py live3-freeze \
  --root /absolute/new-live3-root --seed-sample ./catalog-seeds.json \
  --orcid-policy ./official-ORCID-policy.json --scope ./scope.md \
  --scope-url https://github.com/borisboriov/search-for-research/pull/194#issuecomment-6107652850 \
  --deadline 2026-10-11T12:34:36+00:00 --remaining-percent ACTUAL_OFFICIAL_PERCENT
.venv/bin/python scripts/enrichment_glm_runner.py live3-run \
  --root /absolute/frozen-live3-root --remaining-percent ACTUAL_OFFICIAL_PERCENT
```

Новый root один и immutable; прежние roots используются только как ссылки/SHA,
а baseline сравнивается отдельно после live. Результат публикуется в существующем
отчёте/PR после завершения, не предвосхищается этим описанием. Human0, Sol не gold,
email deliverability/readiness/full collector economy не устанавливаются автоматически.
Cron PAUSED, никакого следующего batch или monitor эта постановка не разрешает.

### Результат единственного live3 контроля

Freeze09:57:21UTC на `dd6cbbcb2235dd82d153dd18e16946ea53e013c5`, acquisition
STOP10:12:36UTC11.10.2026. Новый root:
`/Users/boris/Experiments/search-for-research/enrichment-live3-independent-sol-20261011`.
[Метрики из raw/receipts](../metrics/enrichment_live3_independent_sol_20261011.json),
[posthoc сравнение](../metrics/enrichment_live3_posthoc_comparison_v2_20261011.json)
и [отчёт](../reports/enrichment_night_20261009.md#live3-public-collection--glm-candidates--independent-full-source-sol--11102026)
различают collector candidates, raw Sol и принятые пакеты.

| Development случай | GLM candidates | Независимый Sol | Принято после всех guards |
|---|---|---|---|
| Исангулова | 6, включая новый недатированный контакт | Raw оценивает контакт supported; для city ошибочно применена source_metadata2019-12-11 | Пакет отвергнут: `Unsupported metadata date object`; raw не исправлялся |
| Маслов | 0; есть identity refs | Identity supported, affiliation/activity insufficient/unknown | Identity-only пакет; фактов0 |
| Ковалёв | 3: контакт и две темы | Все3usable; контакт undated, личный набор не подтверждён | Один непустой пакет, не human truth |

Все3collector и3Sol runtime завершились; normalized GLM3/3, Sol2/3,
непустой полный путь1/3. Полные saved sources/fragments:4/54,3/104,4/106.
Data/schema prompts162885/387998/275388bytes; rubric instructions дополнительно
10088bytes каждому, суммарно всё укладывается в frozen cap1MB/person.
Sol процитировал7/5/5refs вне выбранных GLM refs; новые atoms он не добавлял.
Метод не менялся после freeze; до него независимое ревью выявило и закрыло
ошибку общего runtime STOP. Внутри live только один профильный date отказ,
без missing statuses, retries, ручного ремонта и новых jobs.

Расход:6logical jobs, cumulative35→41;28observed GLM requests,27sourcecalls,
10search reservations (8nativeZai+2DDG),22HTTP started/reserved. Sol physical
requests не раскрыты. GLM usage405882tokens:181928fresh input+204864cacheRead+
19090output; cacheWrite0, reasoning не раскрыт. Sol232574input (cached0)+8161output
=240735tokens. Wall:GLM672.264s,Sol222.464s. Quota85→84% accountwide;
delta не приписан этому run. Денежный debit/billing и development/review usage
неизвестны; SDK/catalog cost не подменяет стоимость подписки.

Posthoc старые контакты Исангуловой и historical2007 Маслова отсутствуют в новом
корпусе; у Исангуловой/Ковалёва выбраны новые адреса. Это различие retrieval,
не human recall. Старый конфликт двух ORCID Ковалёва не разрешён поддержанным
identity в более узком новом корпусе. **Для следующего контрольного batch
текущая конфигурация не годна:** один date отказ и пропуск известного saved
контакта остаются; качество, переносимость и экономия полного процесса не
доказаны. Human0, deliverability unknown, личная готовность не установлена.
Новые вызовы не назначены; cron PAUSED, source/model/process STOP.

## Sol-assisted контакты: переносимый offline-tested workflow (11.10.2026)

После отказа автономного GLM поиска закреплён отдельный тонкий процесс
`scripts/enrichment_assisted.py`. Поиск выполняет Sol-агент с доступным ему
поисковым инструментом; **этот CLI поиска не предоставляет**. Наличие
`web.run` в приложении не означает его доступность в произвольной CLI-сессии.
Автоматическая часть после передачи наблюдённых URL: существующий `PublicLoader`
→ буквальные кандидаты/проверка source SHA и непрерывных spans → отдельный native
`gpt-6.1-sol/high` без веба и MCP → semantic-v3/date guards → локальные карточки
и прогресс. GLM/fallback/repair не вызываются. Это контактный процесс, не полный
сборщик всех 18 полей. Новых live jobs в этом раунде не было.

### Вход, assisted шаг и команды

Зависимости — текущий `uv.lock`, Python 3.12, штатный `codex` CLI с уже имеющимся
доступом по подписке. Fresh PDF читает locked `pypdf`; HTML — существующий parser.
Общий браузер/Playwright/OCR не нужны. Для известного literal MathNet decoder
есть явный `render_mathnet: true`: код читает наблюдённый script URL по прежней
robots/access policy и проверяет точную поддержанную функцию, не исполняет
произвольный JS. Decoder HTTP учитывается в общем бюджете. Иной рендеринг,
защита сайта, неполные источники и недоступность остаются ограничениями.

До нового live запуска требуется отдельное разрешение выборки, search/HTTP/model
лимитов и deadlines. Этот offline scope его не даёт. Передать Sol-агенту:
«Для фиксированных id/name/institution/ORCID найди публичные персональные страницы
и публикации. Сохрани фактические запросы, наблюдённые URL и происхождение ссылок;
не конструируй неизвестные пути. Не переносить сниппеты или предполагаемые ответы
в доказательства. Requested модель/effort — gpt-6.1-sol/high; фактически не exposed
сведения и стоимость оставить unknown. Передать profiles.json и plan.json коду».
Доступность инструмента поиска подтверждает конкретная агентская среда.

`profiles.json` — список каталоговых профилей с уникальными `id` (1..10).
`plan.json` содержит `schema: sol-assisted-contacts-v1`,
`requested_search_model: gpt-6.1-sol`, `requested_search_effort: high`,
`profiles: [{author_id, sources: [...]}]`. Для каждого source нужны `url`,
`kind` (`direct_http`, `direct_pdf`, `structured_orcid`) и
`discovery: {method, observed_url, note, query}`; method — `agent_search`,
`observed_href` либо `known_orcid`, query обязателен для agent_search.
`observed_url` должен буквально совпадать с URL. Это запись агента о поиске,
**не независимое доказательство физического search call**. Сохранять доступные
tool receipts отдельно; неизвестный транспорт, physical calls и usage не выдумывать.

`scope.json` содержит `authorization_reference`, `live_authorized` (для offline
fixture — false), timezone-aware `deadline_acquisition` и `deadline_verification`,
целые `HTTP_total_cap` (1..200), `HTTP_per_profile_cap` (1..30), `remaining_stop`
(0/5/15; значение0 только по прямому разрешению), при ORCID — `ORCID_policy` с
`access: allowed`, `source: https://pub.orcid.org/v3.0` и сохранённым основанием.
Числа — верхние возможности CLI; фактический разрешённый scope может быть строже.
Model cap фиксируется числом профилей, один независимый Sol на профиль.

```sh
.venv/bin/python scripts/enrichment_assisted.py prepare \
  --root /absolute/new-authorized-root --profiles /absolute/profiles.json \
  --plan /absolute/plan.json --scope /absolute/scope.json
.venv/bin/python scripts/enrichment_assisted.py dry-run --root /absolute/new-authorized-root
.venv/bin/python scripts/enrichment_assisted.py status --root /absolute/new-authorized-root
# Только после отдельного live разрешения и официальной сверки остатка:
.venv/bin/python scripts/enrichment_assisted.py run --live \
  --root /absolute/new-authorized-root --remaining-percent ACTUAL_OFFICIAL_PERCENT
```

Последняя строка — **одна команда для доступных автоматических стадий** после
assisted поиска. `prepare` фиксирует sample/plan/scope/policy/code/lock/rubric SHA,
ничего не вызывает; `dry-run` проверяет freeze и выводит progress. `run` использует
один writer lock, долговечные HTTP reservations/native receipts. Завершённые
outputs повторно проверяются без calls; неизвестный started job никогда не
повторяется. Root/parent STOP запрещает новые jobs. Старые terminal roots не
возобновляются. При недоступном источнике/guard/deadline команда останавливается
с сохранёнными промежуточными файлами: это не обещание полного покрытия каждого
профиля. Возобновление того же разрешённого незавершённого root допускается лишь
при прежнем freeze и guards; нельзя менять caps/удалять STOP или unknown attempt.

Буквальная нормализация ограничена пробелами вокруг `@`, без OCR или угадывания.
Кандидаты сохраняют непрерывный локальный контекст, source URL/representation/
bytes/text/registry SHA. Sol получает все static fragments реально прочитанных
источников, включая контекст, который сборщик не выбрал; cap кандидатов32/source
не доказывает полноты контактов. Весь prompt с rubric должен помещаться в1MB:
превышение останавливает профиль, не обрезает evidence. Raw/schema/date failures
не исправляются и не получают автоматической повторной модели. Карточки выдаются
только после всех обязательных guards; saved native output и validated result
показаны раздельно. Usage completed native jobs — из receipts; search/development/
review usage, реальный подписочный debit и доллары неизвестны, пока не измерены.

### Пересоздать baseline карточки без вызовов

Команда `saved` читает sealed flexible10 и allowlisted исторический PDF parser,
проверяет оба transfer index и их mapped files, prepared input/source binding и
полные старые semantic-v3 classifications. Исторические verdicts/45atoms не
пересуждаются и не выдаются за результаты новых date guards. Новый packet показывает
все10профилей: выбранные8личныхконтактов (3historical/5undated), два случая без
принятого контакта с причинами отказа кандидатов. Новая человеческая проверка ещё
не состоялась. Старые исходники, metrics, STOP, Pi12/live3/ранние humanrecords
остаются отдельными.

```sh
.venv/bin/python scripts/enrichment_assisted.py saved \
  --root /absolute/new-human-packet-root \
  --baseline /absolute/enrichment-flexible10-20261010 \
  --index /absolute/enrichment-flexible10-20261010/transfer-SHA-index-d7883ed.json \
  --index-sha256 051331260c38f35cadbf3580cbddec217710a00550dde97791b73b36bdc251fc \
  --legacy-pdf-root /absolute/enrichment-glm-remaining6-20261011 \
  --legacy-index /absolute/enrichment-glm-remaining6-20261011/transfer-SHA-index-92482b6.json \
  --legacy-index-sha256 a8413a08783b48e56fb46e5b9e4710c16a5d3b8bd63aa19683f9f2e75154dd85
```

Открыть выведенный `human-v3/packets/baseline-contacts/review.html` локально.
Для реально просмотренного контакта записать общее решение и отдельно text
(цитата), identity (принадлежность), current (согласие с historical/undated оценкой).
«Недостаточно оснований» разрешено по каждой оси: это не подтверждение текущей
доставляемости. Комментарий позволяет пояснить сомнение или дату. Не просмотренные
контакты не включать. Для двух профилей без принятого контакта answers не требуются;
отсутствие принятого контакта не доказывает его отсутствия у человека.

Ввести фактическое имя/минуты, подтвердить личный просмотр и нажать «Скачать мои
решения». Автосохранения/отправки нет; скачать до закрытия страницы. Полученный
`baseline-contacts-human.json` передать Борису/продуктовому потоку как локальный
файл; импортировать **в отдельный новый private root**, а не в sealed baseline:

```sh
.venv/bin/python scripts/enrichment_human.py import \
  --root /absolute/separate-human-answers-root \
  --manifest /absolute/new-human-packet-root/human-v3/packets/baseline-contacts/manifest.json \
  --answers /absolute/baseline-contacts-human.json --record-id boris-baseline-contacts
```

Контракт прежний `human_answers_v3`: packet SHA, claim IDs, реальные attestation/
время, частичные answers; selected contact mode требует все3оси и отвергает скрытые
claim IDs. Record помечен `review_scope: selected_personal_contacts`;
`total_claims` — выбранные contacts, `total_original_claims` — исходные atoms.
`all_selected_claims_reviewed` не означает `all_original_claims_reviewed` или
приёмку профиля, а отсутствие человеческих ответов не превращается в gold.
Email не означает набор студентов. Ответы с именем/заметками не публиковать в git.

[Результат offline проверки](../reports/enrichment_night_20261009.md#sol-assisted-workflow-и-baseline-contact-cards--11102026)
и [сгенерированные агрегаты](../metrics/enrichment_sol_assisted_offline_20261011.json)
фиксируют границу: mocked automatic pipeline и реальный saved export проверены,
новый live assisted end-to-end запуск, массовая экономия и качество после human
приёмки ещё не доказаны.
