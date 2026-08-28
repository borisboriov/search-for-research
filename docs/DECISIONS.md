# DECISIONS — журнал решений (ADR-lite)

Формат: дата — решение — почему — альтернативы.

## 2026-08-28 — uv workspace с виртуальным корнем

Корневой `pyproject.toml` без build-system (сам по себе не пакет), два
workspace-пакета `sfr-core` и `sfr-etl` с hatchling. Dev-зависимости — в
dependency-group `dev` корня.
**Почему:** корень не содержит кода; hatchling — стабильный минимальный бэкенд.
**Альтернативы:** uv_build (моложе, меньше документации), setuptools (тяжелее).

## 2026-08-28 — конфиги инструментов в корневом pyproject.toml

ruff/mypy/pytest/coverage настроены один раз в корне, а не по-пакетно.
Разная строгость mypy — через per-module override (`sfr_core.*` strict).
**Почему:** один источник настроек, `make lint`/`typecheck`/`test` работают из корня.
**Альтернативы:** по-пакетные конфиги — дублирование и рассинхрон.

## 2026-08-28 — пин Python 3.12 (.python-version)

На macOS uv помечает `.venv` флагом `hidden`, а Python 3.13 (site.py) пропускает
hidden `.pth`-файлы — editable-пакеты workspace переставали импортироваться.
**Почему:** Python 3.12 не имеет этой проверки; SPEC требует «3.12+», CI и так на 3.12.
**Альтернативы:** `chflags nohidden` после каждого sync (хрупко), не-editable установка
(неудобно при разработке).

## 2026-08-28 — сверка с реальным OpenAlex API (пробные запросы)

Расхождения со SPEC/ожиданиями, зафиксированные по фактическим ответам:

- У Institution **нет поля name_ru**: русское название лежит в
  `display_name_alternatives` (у МФТИ `international.display_name.ru = null`).
  Решение: `name_ru` = первая кириллическая строка из `display_name_alternatives`, nullable.
- У Author `last_known_institutions` — **список** (у одного автора до 3+ институтов),
  а не единственный FK. Решение: в БД храним один FK — целевой институт ингеста
  (тот, по которому автор был найден); полный список остаётся в `raw` JSON.
- Метрики автора лежат в `summary_stats` (`h_index`, `i10_index`, `2yr_mean_citedness`).
- Фильтр авторов по вузу: используем `last_known_institutions.id:<ID>` (у МФТИ 7649
  авторов) — «текущая» аффилиация релевантнее для подбора НР, чем историческая
  `affiliations.institution.id`. Сортировка `works_count:desc`, cursor-пагинация
  (`meta.next_cursor`) — подтверждены.
- Работы: `abstract_inverted_index` (nullable), `topics[].score`, `title == display_name`,
  параметр `select=` работает — используем для сокращения трафика.
- «Свежесть» публикации автора на этапе ингеста авторов определяем по `counts_by_year`
  (годы с `works_count > 0`), т.к. работ в БД ещё нет; порядок элементов не гарантирован —
  фильтруем по значению года. «Последние N лет» = календарные годы `>= current_year - N + 1`.
- Данные: топ по works_count — участники мегаколлабораций (напр. «A. Zhemchugov»,
  2847 работ, h=152, 100+ соавторов на работу) — кандидаты в проблемы качества для REPORT.

## 2026-08-28 — coverage: исключены CLI-обвязка и alembic

`omit = ["*/sfr_etl/cli.py", "*/alembic/*"]` — порог ≥80% считается по чистой
логике, как требует §5 SPEC («не считая CLI-обвязку и alembic»).
