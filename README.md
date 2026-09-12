# Search For Research

Сервис кросс-вузового подбора научных руководителей: студент описывает научные
интересы → получает 5–10 релевантных НР (embedding-поиск по их публикациям).

**Итерация SFR-0** — фундамент монорепы + ETL-пайплайн: OpenAlex → профили
научных руководителей → SQLite + JSONL-экспорт для будущего embedding-поиска.

**Итерация SFR-1** — мини-тест embedding-моделей: пакет `sfr-match` (индекс, поиск,
eval-харнесс), golden set из 30 запросов студентов, сравнение 5 вариантов
(4 модели + BM25) × чистка profile_text. Результат — `docs/SFR1_REPORT.md`.

**Итерация SFR-2** — сервис поиска: `apps/api` (FastAPI `/api/match`), контейнер,
FAISS на пути поиска в Linux, перекалиброванный порог «мы никого не нашли» и
эксперимент о том, что класть в индекс. Результат — `docs/SFR2_REPORT.md`.

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
| `make eval-sfr1` | Прогон мини-теста SFR-1. **Перезаписывает замороженный `docs/SFR1_REPORT.md`** — см. `docs/DECISIONS.md` |
| `make eval-report` | Только перегенерация `docs/SFR2_REPORT.md` |
| `make test-slow` | Смоук-тест с настоящей моделью (не гоняется в CI) |
| `make index-sfr2` | Шесть индексов SFR-2: frida/mpnet × три состава `profile_text` |
| `make eval` (= `make eval-sfr2`) | Воспроизведение всех цифр `docs/SFR2_REPORT.md` (нужны индексы) |
| `make api` | uvicorn на `localhost:8000` |
| `make docker-build` / `make docker-up` / `make docker-down` | Контейнер с API |
| `make bench` | Замер ресурсов и латентности → `docs/sfr2_resources.json` |
| `make catalog-sfr5` | Пересборка каталога из БД: склейка дублей, профили, экспорты |
| `make index-sfr5` | Боевой индекс каталога 12 вузов (`data/indexes_sfr5`) |
| `make eval-sfr5` | Регрессия на новом корпусе: golden + OOD, судейские пулы |

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

### Каталог 12 вузов (SFR-5)

```bash
uv run sfr institutions resolve "ITMO University"
uv run sfr etl authors --institution I173089394 --strategy stratified --quota 500
uv run sfr etl works --institution I173089394     # сеть: см. предупреждение ниже
make catalog-sfr5 && make index-sfr5 && make eval-sfr5
```

Отбор авторов идёт не «верхушкой по числу работ», а квотой с раскладкой по
областям OpenAlex (`sfr_etl/catalog.py`); дедупликация и детектор чужих склеек —
`sfr_etl/dedup.py`, выборка на ручную проверку — `packages/sfr-match/eval/dedup_for_review.md`.

⚠️ **Ингест работ идёт в два шага.** У OpenAlex дневная квота: анонимно
$0,10/сутки (1 000 list-запросов), с бесплатным ключом — $1/сутки (10 000).
Полный каталог стоит 10 014 запросов, то есть одну дневную квоту с ключом
(`OPENALEX_API_KEY` в `.env`).

```bash
uv run python scripts/warm_works_cache.py   # сеть: греет кэш, ~23 мин, стоп на 429
uv run sfr etl works --only-missing         # запись в БД по кэшу, без сети
```

Подробности — `docs/SFR5_REPORT.md` §3 и `docs/DECISIONS.md`.

### Сервис поиска (SFR-2)

```bash
make index-sfr5                              # офлайн-сборка индекса (API его не строит)
make api                                     # или make docker-up
curl -s localhost:8000/api/health | jq
curl -s localhost:8000/api/match -H 'content-type: application/json' \
  -d '{"query":"нейросети для медицинских изображений","k":5}' | jq
```

Подробности — `apps/api/README.md`. Настройки сервиса: переменные `SFR_API_*`.

## Структура

```
packages/sfr-core/   # доменное ядро: модели SQLAlchemy, настройки, схемы экспорта
packages/sfr-etl/    # клиент OpenAlex, ингест, сборка профилей, CLI `sfr`
packages/sfr-match/  # индекс, поиск, eval-харнесс, CLI `sfr-match`
                     #   eval/ — golden set и судейские оценки (в git, это актив)
apps/api/            # FastAPI-сервис поиска (SFR-2): /api/match, /api/supervisors, /api/health
apps/web/            # заглушка под SFR-3 (Next.js)
scripts/             # bench_api.py — замер ресурсов контейнера
data/                # gitignored: raw-кэш API, SQLite, экспорты, индексы, прогоны eval
docs/                # DECISIONS.md (ADR), SESSIONS.md, SFR<N>_REPORT.md, specs/; правила issues — CLAUDE.md
```

Требования: Python 3.12+, [uv](https://docs.astral.sh/uv/).
