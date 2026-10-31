# Карта документов Search For Research

Вход — [бриф](product/brief.md), поручение и связанные issues/PR; затем нужный источник ниже. Принятое читаем в main, исследование в рабочей ветке — с её статусом. [AGENTS](../AGENTS.md) задаёт роли, разрешения и процедуры; здесь их не повторяем.

## Рабочие источники

| Информация | Основной источник и кто обновляет |
|---|---|
| Общее принятое состояние | [brief.md](product/brief.md); продуктовый поток после приёмки общего решения/результата |
| Требования продукта | [MVP-спека](product/mvp_spec.md), постановка текущей задачи; автор порученной правки, общие изменения принимает продуктовый поток |
| Причина решения | [DECISIONS](DECISIONS.md): сводка и нужная датированная запись, не вся история |
| Учебная рамка | [НИР и ВКРС](product/nir_vkrs.md); требования — [НИР 3](product/course_grading_NIR3.md) и [предзащита/ГИА](product/course_grading_VKRS.md); автор темы, согласование НР отделено от ЛМС |
| Личная НИР Бориса | [Текущая постановка и основания методики](product/research/profile_evidence_review_2026-10.md); план и статус — [#154](https://github.com/borisboriov/search-for-research/issues/154) |
| Монетизация и другие исследования | [Продуктовые материалы](product/README.md); автор темы обновляет выводы в одном источнике, гипотезы не становятся принятыми параметрами |
| Техническое обогащение | [Модуль](../enrichment/README.md), [методики, измерения и архивы](../enrichment/research/INDEX.md); автор запуска. НИР ссылается на эти доказательства, не копирует корпус |
| Задачи / доказательства реализации | [Issues](https://github.com/borisboriov/search-for-research/issues) / соответствующий PR; [доска](https://github.com/users/borisboriov/projects/5) производна от задач |

Текстовые рабочие оригиналы — этот репозиторий; тематический указатель — [product/README](product/README.md). Закрытые спеки в `specs/`, активная спека — в корне. Измерения, разметка, отрицательные результаты и снимки сохраняются по ссылкам ниже. `SESSIONS.md` и `product/brief_history_qa.md` заморожены, новые пересказы сессий туда не добавляются.

## Локальные оригиналы и публикация

Папка `~/Desktop/Search for Research` имеет собственный AGENTS. `01_core/` хранит паспорт, питч и обоснование: самостоятельные документы разных аудиторий, не лишние копии. Паспорт содержит закреплённые формулировки и цифры; финансовые изменения — только по решению Бориса. Автор локальной правки сохраняет прежнюю версию в `03_archive/` и проверяет затронутые связи.

В `01_core/custDev/`: `CustDev.xlsx` — исходный раунд; `CustDev_обезличенный.xlsx` — его версия для передачи; `CustDev — раунд 2.xlsx` — рабочий оригинал R02. Они не взаимозаменяемы. Автор интервью ведёт текущий раунд; персональные данные остаются локально, в Git/витрине — только обезличенные выводы. Закрытые материалы монетизации читаются по локальному указателю `02_research/monetization/README.md`.

`02_research/` хранит исходники исследований, `03_archive/` — прежние версии и доказательства. Учебный комплект `nir/Search For Research_ВКРС` самостоятельный для каждого этапа; навигация — `nir/README.txt`. [Google Drive](https://drive.google.com/drive/folders/19pFtXT0ZwgX30UjKgWZRLKFKIWp9vogz) — опубликованная витрина, не оригинал. Обновляет Борис с сохранением ссылок; до подтверждения публикации и доступа соответствующая issue открыта. GitHub не заменяет доступ комиссии.

## Что проверяется автоматически

`make docs-check` проверяет выбранные живые документы: пути, внутренние Markdown-ссылки/якоря, согласованность брифа с `ApiSettings`, доступным `meta.json` и указанными метриками. Он не устанавливает истинность источника или принятие гипотезы; внешние сайты и частные локальные файлы не обходит.

Публичный `/api/health` закрыт (404), поэтому `make docs-check-live` не является рабочей проверкой production. `python3 scripts/docs_check.py --live --url http://127.0.0.1:8000/api/health` применим только при доступном внутреннем API. Проверка на VPS — по [deploy/README](../deploy/README.md), без открытия API наружу.

## `reports/` — отчёты итераций

| Файл | Что | Как появился |
|---|---|---|
| `REPORT.md`, `REPORT_notes.md` | SFR-0: статистика ETL, примеры `profile_text`, проблемы данных | **генерируется** `make report` (`sfr report`); `_notes` — руками |
| `SFR1_REPORT.md`, `SFR1_REPORT_notes.md` | SFR-1: выбор модели (FRIDA) | **генерируется** `sfr-match report`, `_notes` дописывается как есть; заморожен |
| `SFR2_REPORT.md`, `SFR2_REPORT_notes.md` | SFR-2: API, пороги, состав индекса | **генерируется** `sfr-match report-sfr2` (последний шаг `make eval`); заморожен — перезапуск перезапишет |
| `SFR3_REPORT.md` … `SFR6_REPORT.md`, `SFR4b_REPORT.md`, `SFR5b_REPORT.md`, `SFR5c_REPORT.md` | отчёты итераций | пишутся руками, числа — из `metrics/` и прогонов |
| `BACKLOG_2026-09_REPORT.md` | сессии 27.09: бэклог ревью 12–13.09 и дедупликация-2 (PR #139); чистка eval (#143) | руками |
| `GH_MIGRATION_REPORT.md` | перенос задач из markdown в GitHub Issues (12.09) | руками |
| [pilot-ui-validation.md](reports/pilot-ui-validation.md) | UI-пакет #155–161: проверки, снимки, принятые тексты; [проверка top-100 переводов с источниками](reports/pilot-ui-topics-top100.md) | принято Борисом, влито PR #178 |
| [poc-analytics.md](reports/poc-analytics.md) | PoC #162–164: PostgreSQL, события, надёжная доставка, операторские отчёты/backup и репетиция | репетиция и доказательства; актуальный статус — [бриф](product/brief.md), ревью и приёмка — [PR #179](https://github.com/borisboriov/search-for-research/pull/179) |
| [ui-analytics-deploy-20261003.md](reports/ui-analytics-deploy-20261003.md) | Выкладка принятого UI и PostgreSQL: текущий сервер, сохранность, smoke, ресурсы, restore и внешние копии | эксплуатационные доказательства; приёмка — PR #183 |
| [ranking17_20261003.md](reports/ranking17_20261003.md) | Ограниченный эксперимент FRIDA против фиксированного гибрида с BM25; текущий поиск сохраняется | измерения и свежая слепая оценка Astra/max; продуктовая приёмка и merge — [PR #185](https://github.com/borisboriov/search-for-research/pull/185) |
| [nir_email_preparation_20261031.md](reports/nir_email_preparation_20261031.md) | Подготовка замороженных входов, независимой разметки и парного анализа B/C | offline-инструмент; реальный пилот и научный результат отсутствуют, PR #225 |

Независимый ревьюер возвращает результат координатору; тот сохраняет итог
в PR с проверенными base/head и ссылками на оставшиеся находки. Отдельный
REVIEW-файл по умолчанию не создаётся. Для техитерации краткий итог также
включается в существующий отчёт; обычная правка документов нового отчёта не требует.

## `metrics/` — JSON метрик

Руками не править: каждый файл — выход команды, и отчёт ссылается на него как на
воспроизводимый артефакт. Папку больше не переносим (решение 27.09: второй
перенос дороже пользы).

| Файл | Команда |
|---|---|
| `poc_analytics_rehearsal.json` | `scripts/collect_analytics_proofs.py --source data/analytics-rehearsal --out docs/metrics/poc_analytics_rehearsal.json` — безопасные агрегаты из локальной репетиции |
| `sfr2_resources.json` | `make bench` (`scripts/bench_api.py`) |
| `sfr4_bench.json`, `sfr4_bench_prod.json` | `scripts/bench_sfr4.py` (локально / против боевого адреса) |
| `sfr5_metrics.json` | `scripts/analyze_sfr5.py` на путях SFR-5 (блок SFR-5 в Makefile заморожен) |
| `sfr5b_metrics.json`, `sfr5b_resources.json` | `scripts/analyze_sfr5.py` и `scripts/bench_api.py` на путях SFR-5b |
| `sfr5b_decision_metrics.json` | `scripts/sfr5b_decision_metrics.py` |
| `sfr5b_pool_census.json` | перепись пулов OpenAlex 17.09 (продуктовый тред), в этой итерации не перепроверялась |
| `sfr5c_metrics.json`, `sfr5c_decision_metrics.json`, `sfr5c_rejudge_classes.json`, `sfr5c_rejudge_v2_v3.json` | `make metrics-sfr5c` — по архиву измерения 9 010, байт в байт |
| `sfr5c_deploy_metrics.json`, `sfr5c_deploy_interval.json` | `make metrics-deploy-sfr5c` — слепой пересуд выложенного индекса 9 002; интервал Success@k по спорным парам (#131) |
| `sfr5c_base_blind_metrics.json`, `sfr5c_base_blind_interval.json`, `sfr5c_blind_overlap_classes.json` | `make metrics-base-blind-sfr5c` — слепой пересуд индекса 5 538 (#122) и его интервал |

## Откуда нельзя брать цифры

- **Цифры качества для паспорта и защиты** — только слепой судья:
  `reports/SFR5c_REPORT.md` §13.5 и §13.11, `metrics/sfr5c_deploy_metrics.json`;
  действующие значения с условиями — раздел «Где мы сейчас» `product/brief.md`.
  Колонки «накопленная разметка» и все абсолютные Success@k отчётов до 26.09
  получены судьёй, который сам собирал каталог, — они для сравнения отчётов между
  собой, не для внешних документов (`DECISIONS.md` 26.09, канонический судья).
- **§4 и §6 `SFR5c_REPORT.md`** — измерение каталога **9 010**, а выложен 9 002
  (§13). Действующие числа — §13.
- **Пороги** принадлежат паре модель×индекс: действующие — в `ApiSettings`
  (`apps/api/src/sfr_api/settings.py`), `/health` и §13.4 `SFR5c_REPORT.md`; числа из
  отчётов SFR-2, SFR-5, SFR-5b — пороги своих индексов.
- **nDCG между отчётами несравним** (судейский пул разный); Success@k — только на
  неизменных наборах 22 и 24.
- **Калибровочные таблицы SFR-5, SFR-5b и OOD-блок §4 SFR-5c** считались на 19
  посторонних; действующий набор — 17 (`DECISIONS.md` 26.09). Воспроизводить их —
  с архивным набором (`make metrics-sfr5c`, `make ood19-sfr5c`).
- **Генерируемые отчёты** (`REPORT.md`, `SFR1_REPORT.md`, `SFR2_REPORT.md`)
  переписываются своими командами — править их руками бессмысленно.
- **Review-выборки в `data/eval/review/`** — рабочие выходы целей и CLI, каждый
  прогон их переписывает; доказательство — только файлы
  `packages/sfr-match/eval/` из таблицы «Доказательства» его README (#143).
- **Цифры-деньги** (рынок, стоимость хостинга) — не менять без решения Бориса
  (`product/market_stretch_map_2026-08-08.md`); `03_archive/` папки документов —
  не источник цифр.

## Старые пути

Закрытые issues, спеки и датированные записи могут ссылаться на прежние пути. [Карта перемещений до этой редакции](https://github.com/borisboriov/search-for-research/blob/e3782e284f27ad0adf32ebb54f1471520a4af1b7/docs/README.md#старые-пути) сохранена в Git; история отдельного файла — `git log --follow`. Историческую ссылку не подменяем текущим измерением.
