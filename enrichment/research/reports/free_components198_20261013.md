# Бесплатные компоненты на frozen10 — #198, часть A, 13.10.2026

## Результат и решение

На тех же **25 сохранённых источниках / 10 профилях** готовые локальные парсеры
не заменили проверку принадлежности. Control + pypdf восстановили буквальные
кандидаты для **5/8** известных human-контактов; bs4/lxml + pdfplumber дают те же
пять. Это знакомая диагностическая выборка, не blind/prevalence и не проверка
спроса. Поддерживаемый live default не изменён.

**Рекомендация:** сохранить текущие control/pypdf; bs4/lxml и pdfplumber оставить
резервом. Trafilatura оставить резервом для очистки текста, но не единственным
контактным extractor. FindYourProfessor 0.2 отвергнуть как замену конвейера;
небольшая чистая функция проверена, полный scraper не запускался. ORCID JSON
пригоден для структурированных публичных полей без модели, но здесь email нет.
GROBID, Scrapy и Crawl4AI — недостаточно данных: явно не проверены.

Часть B: Яндекс ожидает подключения/отдельного разрешения расходов. Платных
сервисов, аккаунтов/биллинга, SMTP и production изменений нет; issue #198 целиком
не закрывается. Работа/постановка/CI/финальное ревью — [PR #200](https://github.com/borisboriov/search-for-research/pull/200).

## Входы, freeze и условия

Base `897a7b6b0f002581cb9f34dfb2c1aa809bcf83e3`, PR #194 влит; origin/main
обновлён перед собственным worktree. Начало 13.10 20:01:08 МСК, предел реализации
и измерений — 14.10 00:01:08 МСК. Этот отчёт описывает только часть A.

Точные private baseline/human paths — [artifact catalogue из INDEX](../INDEX.md).
Baseline root `enrichment-flexible10-20261010`; источники взяты из 25 `source-*.json`,
ссылки на оригинальные bodies/decoded вместо копирования. **273 source mapped
файла** сверены с историческим transfer-SHA-index-d7883ed.json: расхождений 0.
Все raw/decoded SHA дополнительно сверены перед replay. Старые roots/STOP/seals,
разметка и metrics не менялись. Три формата: 11 HTML, 4 PDF, 10 ORCID JSON.
Российская принадлежность — аффилиация каталога, не фамилия/язык/.ru; источник
Maslov — историческая американская работа с прежним конфликтом аффилиации.

Новый private root: `/Users/boris/Experiments/search-for-research/enrichment-free198-20261013`.
`run-v2/manifest.json` заморозил до replay версии, лицензии/classifiers, общие
правила, SHA скрипта, всех runtime файлов и 25 входов. Replay отдельно от human;
evaluate после него сверяет только human8 text+identity agree. `current uncertain`
сохранён. Ни baseline email, ни вердикты не вошли в правила извлечения.
`run-v1` сохранён: исходная оценка не выводила FYP-строки; v2 исправляет таблицу,
полные quote атрибутов и проверки freeze, без нового правила поиска email.
В v1/v2 буквальные наборы по инструментам совпадают. Время v2 — повтор в тёплом
кэше, не обещание cold-start производительности.

Общие правила: текущий EMAIL regexp на видимом тексте; control дополнительно
сохраняет mailto и same-host image query. Bs4/lxml: visible text + mailto.
Trafilatura 2.3.1: стандартный plain text, без отдельного mailto pass. FYP: только
`extract_emails` на raw HTML (11 входов), без keyword фильтра и discovery.
PDF: стандартный page.extract_text, без OCR/склейки переносов. ORCID: только
person.emails с public visibility, не email внутри works. Ни один extractor не
принимает кандидата как личный автоматически. Это контроль extractor, не replay
всего прежнего Sol-assisted конвейера и его Math-Net rendering/семантики.

Сеть заблокирована в replay; физических HTTP к источникам 0, профильных
GPT/GLM/Astra jobs 0. Поиск новых URL/профилей не выполнялся. Документационные
web-чтения и загрузка пакетов — отдельно от source HTTP. Не выдаём заданные URL
за самостоятельное обнаружение.

## Версии и лицензии

| Компонент | Версия | Лицензия | Основание/проверенный режим |
|---|---|---|---|
| BeautifulSoup | 4.15.0 | MIT | installed metadata; visible text/mailto |
| lxml | 6.1.3 | BSD-3-Clause | installed metadata; HTML parser bs4 |
| Trafilatura | 2.3.1 | Apache-2.0 | installed metadata и [upstream](https://github.com/adbar/trafilatura) |
| pypdf | 6.19.0 | BSD-3-Clause | workspace lock / installed metadata |
| pdfplumber | 0.11.10 | MIT | installed classifier/license file и [upstream](https://github.com/jsvine/pdfplumber) |
| FindYourProfessor | 0.2 | MIT | installed classifier и [PyPI](https://pypi.org/project/FindYourProfessor/) |
| GROBID | не установлен | Apache-2.0 | [upstream](https://github.com/grobidOrg/grobid); нужен server/JDK/models, setup не начат |
| Scrapy | не установлен | BSD-3-Clause | [upstream](https://github.com/scrapy/scrapy); loading не проверен |
| Crawl4AI | не установлен | Apache-2.0 | [upstream](https://github.com/unclecode/crawl4ai); browser loading не проверен |

Изолированный [requirements.lock](../components/requirements.lock) включает exact
versions и package hashes; рабочие pyproject/uv.lock не менялись. В manifest
pdfplumber/FYP License field пуст, MIT находится в сохранённых classifiers и
дистрибутиве; это не неизвестная лицензия. Лицензионная/API плата опыта — 0 ₽.

## По форматам и инструментам

Число кандидатов — уникальные пары профиль×email внутри инструмента, а не
число вхождений. Форматные знаменатели human8: HTML 6, PDF 2; в ORCID нет
известных baseline email. Отсутствующий формат в профиле — пропуск, не потеря.

| Tool / формат | Источников | Кандидатов | Восстановлено human8 | Ошибок | wall, с | CPU, с |
|---|---:|---:|---:|---:|---:|---:|
| bs4-lxml | 11 | 27 | 3 | 0 | 0.142 | 0.133 |
| control | 11 | 27 | 3 | 0 | 0.108 | 0.108 |
| findyourprofessor | 11 | 22 | 2 | 0 | 0.024 | 0.022 |
| orcid-json | 10 | 0 | 0 | 0 | 0.021 | 0.021 |
| pdfplumber | 4 | 13 | 2 | 0 | 4.226 | 4.211 |
| pypdf | 4 | 13 | 2 | 0 | 1.539 | 1.505 |
| trafilatura | 11 | 19 | 3 | 0 | 0.453 | 0.425 |

Таблица по 10 профилям: `кандидатов / найдено известного human8`.
`—` означает нет такого формата; ORCID у каждого: 1 источник, 0 email.
Автоматически принятых контактов для каждого инструмента/профиля — **0**;
совпадение с human8 показывает восстановление прежнего доказанного литерала,
а не новое принятие профиля или current. Машинная полная таблица —
[metrics](free_components198_metrics.json), включая dates/current и sources.

| Профиль | Control | bs4/lxml | Trafilatura | FYP | pypdf | pdfplumber |
|---|---:|---:|---:|---:|---:|---:|
| A5070748575 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 1 / 1 | 1 / 1 |
| A5047877230 | 1 / 0 | 1 / 0 | 0 / 0 | 1 / 0 | — | — |
| A5006480668 | — | — | — | — | 5 / 1 | 5 / 1 |
| A5011172734 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | — | — |
| A5069670094 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | — | — |
| A5054791318 | 1 / 0 | 1 / 0 | 0 / 0 | 1 / 0 | 7 / 0 | 7 / 0 |
| A5065694561 | 19 / 1 | 19 / 1 | 13 / 1 | 19 / 1 | — | — |
| A5054586424 | 5 / 1 | 5 / 1 | 5 / 1 | 0 / 0 | — | — |
| A5089458364 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | — | — |
| A5042154547 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 | — | — |

## Потери, ложные добавления и принадлежность

Базовые **8** — human подтвердил текст и identity, а не весь профиль и не
нынешнюю актуальность. Их loss у control+pypdf: **3**; восстановлены **5**
(3 historical, 2 undated), current у пяти по-прежнему uncertain.

| Профиль/кейс | Проверка сохранённого источника | Вывод |
|---|---|---|
| Ahmadi-Asl | Авторская PDF-сноска, версия 2024-04-08 | оба PDF parser сохранили известный личный адрес; historical |
| Тушавина | PDF 2019, именованные блоки пяти авторов | известный адрес сохранён; ещё 4 чужих кандидата |
| Nastulyavichus и Исангулова | Math-Net HTML содержит public decode_email в script | все четыре HTML режима теряют оба известных адреса; без выполнения JS |
| Морозов | `e-mail: morozov NBSP @ space …` в HTML | literal regexp теряет известный адрес; новый deobfuscation после результатов не вводился |
| Derkach | МИСИС, отдельные employee blocks | известный адрес сохранён; 12 коллег и 6 служебных кандидатов |
| Maslov | D-Lib November 2007, именованные авторские блоки | control/bs4/Trafilatura сохранили известный адрес; 4 чужих; FYP raw regex потерял все 5, HTML entities |
| Ledovskaya | отдельная страница сотрудника СПбГУ, без даты | все HTML режимы сохранили известный адрес; current uncertain |
| Styrin | Contacts в шапке лабораторного directory | кандидат лаборатории; прежний личный отказ не human gold, новый агентский вывод по месту адреса |
| Kovalev | PDF psychology ORCID отличается; RL PDF email другого автора; MIPT footer Contact us | 6 чужих, 1 лабораторный, 1 обрезанный PDF-фрагмент; не принимать личным по одному имени |

Объединение извлечённых пар profile×email: **40**. Проверка автора-агента по
сохранённым body/decoded/цитатам: **5** совпадают с human8; **26** относятся другим
учёным; **2** лабораторных; **6** институциональных; **1** `alex- / eykkov` PDF
фрагмент. Приватное `run-v2/agent-source-adjudication.json` содержит каждый
кандидат, URL, body SHA, excerpt, категорию и причину; новые human review = 0.
Это агентская атрибуция, не независимый human gold. **35** было бы ложными
личными добавлениями при наивном принятии всех кандидатов; фактических ложных
автопринятий **0**, поскольку принятия нет. Полнота по всем существующим адресам
не измерена. Не называем unmatched автоматически false positive без чтения
источника. Extractors не подтверждают readiness/current/identity новых профилей.

## Ресурсы и экономика

V2: wall **6.540 с**, process CPU **6.439 с**, peak RSS **254394368 bytes** (242.6 MiB), весь последовательный процесс с импортами.
Per-tool время включает первый импорт; порядок фиксирован, общий process peak
не распределяется между инструментами. Нет повторов для статистической
устойчивости и нет отдельного memory benchmark каждого parser.

Изолированная установка: uv reported prepare/download **4m10s**, 35 packages,
локальных генеративных моделей/weights **0**. Новый venv: **113220553 logical /
126763008 allocated bytes**, 3787 regular files в срезе. V1 proofs 193777 logical
bytes; v2 (manifest/replay/evaluation/agent adjudication) **259100 logical bytes**.
Эти размеры — до финальных review/check logs; итоговый срез сохраняется отдельно
`disk-measurement.json`. Shared uv-cache delta не измерен, APFS shared extents не
измерены; allocated не равен физической дополнительной цене на диске. Общие
workspace dependencies для AGENTS checks отдельно и не относятся к parser run.
Полные источники повторно не сохранялись, компактный новый private root.

Source HTTP **0**, модельный inference для извлечения **0**, платные API **0 ₽**,
новый human labour **0 минут**. Разработка/чтение источников/независимый review —
агентская работа, отдельно от 10 профильных Sol jobs baseline. Она не имеет
полного token/cost receipt и не объявляется бесплатной полной экономикой.
Авторская проверка разногласий занимает часть времени сессии, не human labour;
точная длительность именно adjudication не измерялась. Время начала/окончания
работы есть в issue/PR. Baseline **459511 tokens — только 10 Sol verifier jobs**,
без поиска и разработки; ratio total economy и цена полного корректного
контакта из этого baseline не вычисляются. Измеренная внешняя API-плата на
восстановленный известный литерал: 0 ₽ / 5 = 0 ₽, **только API-компонент**;
автоматических корректно атрибутированных новых контактов 0, деление полной
цены на них не определено. Все 40 кандидатов требуют атрибуции; какую их долю
можно обработать без модели в production, этот опыт не установил.

## Непроверенные режимы

GROBID не поднимался: четыре PDF уже читаются текстовыми библиотеками;
сервер/JDK/weights и локальные модели требуют отдельного измерения. Подготовка
0 минут (<45min cap), HTTP/remote consolidation 0, вес установки неизвестен.
Не писать PASS. Scrapy live loading не запускался: первичный вопрос — потери
offline extraction; дополнительное воспроизведение загрузки здесь не обосновано.
Crawl4AI пропущен: для JS Math-Net уже есть сохранённые материалы, новый browser
run не имеет доказанного учёта/жёсткого cap всех внутренних HTTP. Их версии не
присваиваем установленным; произвольный live обход не заменяет поиск. Ни
CAPTCHA/robots/login/paywall/403/429, ни approval не обходились.

## Воспроизводимость и проверка

[Короткий запуск](../components/README.md): exact isolated lock → freeze → replay →
evaluate → export_summary. Private manifest/results/цитаты сохранены в указанном
новом root; SHA этих артефактов находятся в metrics. Rules/входы не правились по
результатам. Повтор всегда в новом root; выводы пишутся create-only. Baseline
corpus не дублируется и не переименовывается.

Обязательные AGENTS checks и независимое ревью проверенной версии находятся в
PR #200; финальный машинный marker хранит точные base/head, а handoff-check
проверяет актуальные CI. Автор прекращает запись перед передачей координатору.
Merge/deploy не выполнены. Для паспорта предлагаемых изменений нет: новые
данные — инженерная диагностика, не принятие продуктовых чисел.

DoD A: одинаковые25/frozen10/форматы ✓; rules/SHA/versions до replay ✓;
кандидаты/принадлежность/date/current отдельно ✓; private provenance по каждому ✓;
затраты/пропуски/unknown ✓; воспроизводимость/INDEX ✓. Непроверенные live/GROBID
не объявляются готовыми. DoD всего #198 не выполнен: часть B ожидает отдельного
разрешения. Полный pipeline без модели/новая выборка/массовый каталог — вне scope.
