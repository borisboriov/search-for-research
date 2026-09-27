# Карта `docs/`

Что где лежит, что генерируется и откуда нельзя брать цифры. Раскладка — с
27.09.2026 (`docs/DECISIONS.md`, запись того же дня).

```
docs/
  README.md            эта карта
  DECISIONS.md         ADR: сводка действующих решений в начале, дальше — записи по датам
  SESSIONS.md          журнал сессий: что сделано, развилки, рефлексия
  PILOT_TEST_GUIDE.md  операционный гайд пилота
  reports/             отчёты итераций
  metrics/             JSON метрик — генерируются скриптами
  specs/               спеки закрытых итераций (история требований, не задание)
  product/             документы стартапа (бриф, спека MVP, ресерчи, гранты, правки паспорта)
```

Спека **открытой** итерации лежит в корне репозитория, после закрытия уезжает в
`specs/`. Задачи — не здесь, а в GitHub Issues и на доске «SFR — задачи».

## `reports/` — отчёты итераций

| Файл | Что | Как появился |
|---|---|---|
| `REPORT.md`, `REPORT_notes.md` | SFR-0: статистика ETL, примеры `profile_text`, проблемы данных | **генерируется** `make report` (`sfr report`); `_notes` — руками |
| `SFR1_REPORT.md`, `SFR1_REPORT_notes.md` | SFR-1: выбор модели (FRIDA) | **генерируется** `sfr-match report`, `_notes` дописывается как есть; заморожен |
| `SFR2_REPORT.md`, `SFR2_REPORT_notes.md` | SFR-2: API, пороги, состав индекса | **генерируется** `sfr-match report-sfr2` (последний шаг `make eval`); заморожен — перезапуск перезапишет |
| `SFR3_REPORT.md` … `SFR6_REPORT.md`, `SFR4b_REPORT.md`, `SFR5b_REPORT.md`, `SFR5c_REPORT.md` | отчёты итераций | пишутся руками, числа — из `metrics/` и прогонов |
| `GH_MIGRATION_REPORT.md` | перенос задач из markdown в GitHub Issues (12.09) | руками |

Временный отчёт ревью — `reports/REVIEW_<итерация>.md` (`/review-iteration`): в git
не идёт, итог переносится разделом «Независимое ревью» в отчёт итерации.

## `metrics/` — JSON метрик

Руками не править: каждый файл — выход команды, и отчёт ссылается на него как на
воспроизводимый артефакт.

| Файл | Команда |
|---|---|
| `sfr2_resources.json` | `make bench` (`scripts/bench_api.py`) |
| `sfr4_bench.json`, `sfr4_bench_prod.json` | `scripts/bench_sfr4.py` (локально / против боевого адреса) |
| `sfr5_metrics.json` | `scripts/analyze_sfr5.py` на путях SFR-5 (блок SFR-5 в Makefile заморожен) |
| `sfr5b_metrics.json`, `sfr5b_resources.json` | `scripts/analyze_sfr5.py` и `scripts/bench_api.py` на путях SFR-5b |
| `sfr5b_decision_metrics.json` | `scripts/sfr5b_decision_metrics.py` |
| `sfr5b_pool_census.json` | перепись пулов OpenAlex 17.09 (продуктовый тред), в этой итерации не перепроверялась |
| `sfr5c_metrics.json`, `sfr5c_decision_metrics.json`, `sfr5c_rejudge_classes.json`, `sfr5c_rejudge_v2_v3.json` | `make metrics-sfr5c` — по архиву измерения 9 010, байт в байт |
| `sfr5c_deploy_metrics.json` | `make metrics-deploy-sfr5c` — слепой пересуд выложенного индекса 9 002 |
| `sfr5c_base_blind_metrics.json`, `sfr5c_blind_overlap_classes.json` | `make metrics-base-blind-sfr5c` — слепой пересуд индекса 5 538 (#122) |

## Откуда нельзя брать цифры

- **Цифры качества для паспорта и защиты** — только слепой судья:
  `reports/SFR5c_REPORT.md` §13.5 и §13.11, `metrics/sfr5c_deploy_metrics.json`.
  Колонки «накопленная разметка» и все абсолютные Success@k отчётов до 26.09
  получены судьёй, который сам собирал каталог, — они для сравнения отчётов между
  собой, не для внешних документов (`DECISIONS.md` 26.09, канонический судья).
- **§4 и §6 `SFR5c_REPORT.md`** — измерение каталога **9 010**, а выложен 9 002
  (§13). Действующие числа — §13.
- **Пороги** принадлежат паре модель×индекс: действующие — в `ApiSettings`
  (`apps/api/src/sfr_api/settings.py`) и §13.4 `SFR5c_REPORT.md`; числа из
  отчётов SFR-2, SFR-5, SFR-5b — пороги своих индексов.
- **nDCG между отчётами несравним** (судейский пул разный); Success@k — только на
  неизменных наборах 22 и 24.
- **Калибровочные таблицы SFR-5, SFR-5b и OOD-блок §4 SFR-5c** считались на 19
  посторонних; действующий набор — 17 (`DECISIONS.md` 26.09). Воспроизводить их —
  с архивным набором (`make metrics-sfr5c`, `make ood19-sfr5c`).
- **Генерируемые отчёты** (`REPORT.md`, `SFR1_REPORT.md`, `SFR2_REPORT.md`)
  переписываются своими командами — править их руками бессмысленно.

## Старые пути

До 27.09.2026 отчёты и JSON лежали прямо в `docs/`, без подпапок (например,
`SFR5_REPORT.md` и `sfr5_metrics.json`). Ссылки в **закрытых** issues, в `SESSIONS.md`, в
датированных записях `DECISIONS.md` и в спеках ведут на старые пути — это
история, её не переписывали. Файлы теперь в `reports/` и `metrics/`; история
файла — `git log --follow -- docs/reports/<файл>`.
