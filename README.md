# Search For Research

Сервис кросс-вузового подбора научных руководителей: студент описывает научные
интересы → получает 5–10 релевантных НР (embedding-поиск по их публикациям).

**Итерация SFR-0** — фундамент монорепы + ETL-пайплайн: OpenAlex → профили
научных руководителей → SQLite + JSONL-экспорт для будущего embedding-поиска.

## Quickstart

```bash
git clone <repo-url> && cd search-for-research
cp .env.example .env            # впишите свой email в OPENALEX_MAILTO
make setup                      # uv sync + pre-commit
uv run sfr institutions resolve "Moscow Institute of Physics and Technology"
make etl                        # авторы → работы → профили → data/exports/profiles.jsonl
```

Отчёт о прогоне: `make report` → `docs/REPORT.md`.

## Команды

| Команда | Что делает |
|---|---|
| `make setup` | Установка зависимостей (uv workspace) и pre-commit хуков |
| `make lint` | ruff check + ruff format --check |
| `make typecheck` | mypy (strict для sfr-core) |
| `make test` | pytest + coverage (порог ≥80%), без integration-тестов |
| `make test-integration` | Контрактный смоук по живому OpenAlex API |
| `make etl` | Полный пайплайн ингеста (нужен предварительный `institutions resolve`) |
| `make report` | Генерация `docs/REPORT.md` |

CLI-пайплайн по шагам:

```bash
uv run sfr institutions resolve "Moscow Institute of Physics and Technology"
uv run sfr etl authors --max 300          # --institution <id> для явного выбора
uv run sfr etl works --since-years 5 --per-author 25
uv run sfr etl build-profiles
uv run sfr export jsonl --out data/exports/profiles.jsonl
uv run sfr report
```

## Структура

```
packages/sfr-core/   # доменное ядро: модели SQLAlchemy, настройки, схемы экспорта
packages/sfr-etl/    # клиент OpenAlex, ингест, сборка профилей, CLI `sfr`
apps/api/, apps/web/ # заглушки под SFR-1/2 (FastAPI, Next.js)
data/                # gitignored: raw-кэш API, SQLite, экспорты
docs/                # DECISIONS.md, REPORT.md, NEXT.md
```

Требования: Python 3.12+, [uv](https://docs.astral.sh/uv/).
