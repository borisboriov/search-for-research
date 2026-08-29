# Search For Research

Сервис кросс-вузового подбора научных руководителей: студент описывает научные
интересы → получает 5–10 релевантных НР (embedding-поиск по их публикациям).

**Итерация SFR-0** — фундамент монорепы + ETL-пайплайн: OpenAlex → профили
научных руководителей → SQLite + JSONL-экспорт для будущего embedding-поиска.

**Итерация SFR-1** — мини-тест embedding-моделей: пакет `sfr-match` (индекс, поиск,
eval-харнесс), golden set из 30 запросов студентов, сравнение 5 вариантов
(4 модели + BM25) × чистка profile_text. Результат — `docs/SFR1_REPORT.md`.

## Quickstart

```bash
git clone <repo-url> && cd search-for-research
cp .env.example .env            # впишите свой email в OPENALEX_MAILTO
make setup                      # uv sync + pre-commit
uv run sfr institutions resolve "Moscow Institute of Physics and Technology"
make etl                        # авторы → работы → профили → data/exports/profiles.jsonl
```

Отчёт о прогоне: `make report` → `docs/REPORT.md` (статистика генерируется,
ручной разбор и DoD-чеклист живут в `docs/REPORT_notes.md` и подклеиваются в конец).

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
| `make index` | Сборка всех индексов SFR-1 (5 вариантов × clean/no-clean) |
| `make eval` | Полный прогон мини-теста: индексы → golden set → пул → отчёт |
| `make eval-report` | Только перегенерация `docs/SFR1_REPORT.md` |
| `make test-slow` | Смоук-тест с настоящей моделью (не гоняется в CI) |

CLI-пайплайн по шагам:

```bash
uv run sfr institutions resolve "Moscow Institute of Physics and Technology"
uv run sfr etl authors --max 300          # --institution <id> для явного выбора
uv run sfr etl works --since-years 5 --per-author 25
uv run sfr etl build-profiles
uv run sfr export jsonl --out data/exports/profiles.jsonl
uv run sfr report
```

### Поиск научных руководителей (SFR-1)

```bash
uv run sfr-match index -m e5-base            # profiles.jsonl → эмбеддинги → data/indexes/
uv run sfr-match search "нейросети для текстов" -m e5-base -k 10
uv run sfr-match eval --models e5-base,bm25  # golden set → data/eval/runs/
uv run sfr-match report                      # → docs/SFR1_REPORT.md
```

Модели: `e5-base`, `mpnet`, `frida`, `minilm`, `bm25` (см. `sfr_match/models.py`).
Флаг `--clean` строит вариант с очищенным `profile_text` (LaTeX-мусор и
«аннотации-списки авторов» — проблемы №1–2 из `docs/REPORT.md`).

## Структура

```
packages/sfr-core/   # доменное ядро: модели SQLAlchemy, настройки, схемы экспорта
packages/sfr-etl/    # клиент OpenAlex, ингест, сборка профилей, CLI `sfr`
packages/sfr-match/  # индекс, поиск, eval-харнесс, CLI `sfr-match`
                     #   eval/ — golden set и судейские оценки (в git, это актив)
apps/api/, apps/web/ # заглушки под SFR-1/2 (FastAPI, Next.js)
data/                # gitignored: raw-кэш API, SQLite, экспорты, индексы, прогоны eval
docs/                # DECISIONS.md, REPORT.md, SFR1_REPORT.md, NEXT.md
```

Требования: Python 3.12+, [uv](https://docs.astral.sh/uv/).
