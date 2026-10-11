# Ограниченный автономный сбор GLM: frozen10

Рабочий CLI: `scripts/enrichment_glm_runner.py`. Native Pi 1.1.0 использует
существующую подписку Z.ai, GLM-5.3-Flash/high выбирает запросы, страницы,
буквальные переходы и факты. Python сохраняет HTTP, кэш, robots, источники,
лимиты и проверяет цитаты. Native Sol 6.1/high проверяет обе отдельные стороны
по полной неизменённой semantic-v3. Человеческих оценок и gold нет.

## Что делал baseline

В flexible10 обычный код загружал ORCID/HTML/PDF, соблюдал ограничения,
извлекал текст, выполнял публичный Math-Net decoder и связывал цитаты с bytes.
Главная сессия Sol выбирала 23 логических запроса через web.run, страницы,
переходы и контекст; одноразовые драйверы сохраняли выбранные планы.
459511 токенов и 645.630 секунды относятся только к десяти проверкам native Sol.
Токены/время главной сессии и внутренняя физическая стоимость web.run неизвестны.
Это не измеренная стоимость автономного сбора baseline.

## Запуск и доказательства

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
