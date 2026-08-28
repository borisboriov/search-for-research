# SFR-0: Стартовая монорепа + пайплайн данных OpenAlex

**Проект:** Search For Research — AI-сервис кросс-вузового подбора научных руководителей (НР).
**Эта итерация (SFR-0):** фундамент монорепы + первый работающий пайплайн данных: OpenAlex → профили научных руководителей МФТИ → база + JSONL-экспорт для будущего embedding-поиска.
**Режим работы:** автономный. Вопросы задавать некому — принимай разумные решения сам и фиксируй их в `docs/DECISIONS.md`.

---

## 1. Контекст продукта (зачем это всё)

Студент вводит описание научных интересов → сервис возвращает 5–10 релевантных НР из разных вузов (embedding search по их публикациям). Будущая архитектура: ETL-пайплайн (офлайн) → PostgreSQL → FAISS + sentence-transformers → FastAPI → Next.js. В этой итерации делаем ТОЛЬКО ETL и фундамент репозитория. Никакого ML, backend-API и фронтенда — но структура репы должна оставить им место.

## 2. Структура монорепы

```
search-for-research/
├── pyproject.toml           # uv workspace root
├── Makefile                 # make setup / lint / test / etl / report
├── .pre-commit-config.yaml
├── .github/workflows/ci.yml # lint + typecheck + tests
├── .env.example             # OPENALEX_MAILTO=..., SFR_DB_URL=...
├── README.md                # quickstart: 5 команд от clone до данных
├── docs/
│   ├── DECISIONS.md         # журнал решений (ADR-lite: дата, решение, почему)
│   ├── REPORT.md            # отчёт о реальном прогоне (генерируется, см. §7)
│   └── NEXT.md              # что делать в следующей итерации (SFR-1: embeddings)
├── packages/
│   ├── sfr-core/            # src/sfr_core/: модели SQLAlchemy, настройки, схемы Pydantic
│   └── sfr-etl/             # src/sfr_etl/: клиент OpenAlex, ингест, сборка профилей, CLI
├── apps/                    # ПУСТО (заглушки-README): api/ и web/ появятся в SFR-1/2
└── data/                    # gitignored: raw-кэш, sqlite, экспорты
```

Инструменты (всё — актуальные версии на момент запуска):
- **uv** (workspace, lock-файл), Python 3.12+
- **ruff** (lint + format), **mypy** (strict для sfr-core, basic для sfr-etl допустим)
- **pytest** + pytest-cov; **respx** или vcr-подход для мока HTTP
- **pydantic-settings** для конфига (env), **structlog** для логов
- **typer** для CLI, **httpx** для HTTP, **tenacity** для ретраев
- **SQLAlchemy 2.x** + **alembic**. БД: SQLite по умолчанию (файл в `data/`), но модели и типы — совместимые с PostgreSQL (в проде будет он). Ни одной SQLite-специфичной фичи.
- pre-commit: ruff, ruff-format, mypy на изменённые файлы
- CI (GitHub Actions): `make lint && make typecheck && make test` на push/PR

## 3. Домен: что такое «профиль НР»

Сущности (SQLAlchemy, + Pydantic-схемы для экспорта):

- **Institution**: openalex_id, ror_id, name_ru/name_en, country. 
- **Author**: openalex_id, orcid (nullable), display_name, last_known_institution (FK), works_count, cited_by_count, h_index, i10_index, is_supervisor_candidate (bool, см. эвристику), fetched_at, raw JSON (провенанс — полный ответ API).
- **Work**: openalex_id, author FK (many-to-many через authorship, но для SFR-0 достаточно связки «в чьём профиле учитываем»), title, publication_year, abstract_text (восстановленный, nullable), topics (JSON), cited_by_count, is_recent (за последние 5 лет).
- **AuthorTopic**: author FK, topic_name, score (из topics/x_concepts автора в OpenAlex).
- **SupervisorProfile** (материализуется при экспорте, можно view/сборкой на лету): author + institution + агрегаты + **profile_text** — главный артефакт: связный текст 300–1500 символов для будущих эмбеддингов: имя, должность/аффилиация, ключевые темы, названия и фрагменты аннотаций 5–10 самых свежих/цитируемых работ. Русский/английский — как есть в источнике, не переводить.

Эвристика `is_supervisor_candidate` (конфигурируемые пороги в settings):
works_count ≥ 10 И есть публикация за последние 3 года И h_index ≥ 5. Отсеянных НЕ удалять — хранить с флагом false (пороги будем крутить).

## 4. Пайплайн (sfr-etl)

CLI: `sfr` (typer), команды:

1. `sfr institutions resolve "Moscow Institute of Physics and Technology"` — найти вуз через OpenAlex search, показать кандидатов, сохранить выбранный в БД. **Не хардкодить ID вуза в коде** — только через resolve (в конфиг/БД).
2. `sfr etl authors --institution <id> --max 300` — авторы с аффилиацией вуза (фильтр по `affiliations.institution.id` / `last_known_institutions.id` — сверься с актуальной документацией API, см. §6-правило), cursor-пагинация, сортировка по works_count desc.
3. `sfr etl works --since-years 5 --per-author 25` — работы для supervisor-candidates: свежие + самые цитируемые; восстановить abstract из `abstract_inverted_index` (отдельная чистая функция + тесты).
4. `sfr etl build-profiles` — собрать SupervisorProfile, посчитать полноту.
5. `sfr export jsonl --out data/exports/profiles.jsonl` — по одной строке на НР: `{id, name, institution, h_index, topics, profile_text, works: [...]}`. Это вход для SFR-1 (embeddings).
6. `sfr report` — сгенерировать `docs/REPORT.md` (см. §7).

Требования к клиенту OpenAlex:
- База `https://api.openalex.org`, **всегда** передавать `mailto` из env (polite pool). Если env пустой — понятная ошибка при старте.
- Rate limit: ≤10 rps, плюс уважать заголовки; ретраи с экспоненциальным бэкоффом на 429/5xx (tenacity).
- **Дисковый кэш raw-ответов** в `data/raw/` (ключ — URL+params hash): повторный прогон не ходит в сеть за тем же. Флаг `--refresh` для сброса.
- Идемпотентность: повторный ингест обновляет записи (upsert по openalex_id), не плодит дубли.
- eLibrary/РИНЦ и любой скрейпинг сайтов — **вне скоупа, не делать**.

## 5. Тесты (обязательная часть, не «если успеешь»)

- Юнит: восстановление abstract из inverted index (включая пустой/битый), эвристика supervisor_candidate (граничные случаи), сборка profile_text (длина, состав, автор без аннотаций), upsert-идемпотентность (на SQLite in-memory), пагинация клиента (мок respx: 2 страницы + 429-ретрай).
- Контрактный смоук (помечен `@pytest.mark.integration`, в CI не гоняется, локально — гоняется тобой): 1 реальный запрос institutions + 1 страница авторов + 1 работа с abstract — проверка, что поля, на которые мы полагаемся, реально существуют.
- Coverage чистой логики (не считая CLI-обвязку и alembic) ≥ 80%. Порог зашить в pytest-cov.
- Все тесты, ruff и mypy — зелёные в CI.

## 6. Правила работы

- **Сверяйся с реальностью, а не с памятью.** Перед использованием полей OpenAlex сделай пробный запрос и посмотри фактический ответ; если схема API отличается от описанной здесь — адаптируйся и запиши в DECISIONS.md.
- Коммиты маленькие, conventional commits (`feat:`, `test:`, `chore:`...). Работай так, будто каждый коммит пойдёт в PR.
- Не выходи за скоуп SFR-0 (никаких embeddings, API, фронта, докера для приложений — docker-compose для Postgres не нужен, SQLite достаточно).
- Секреты только через env; `.env` в gitignore; `.env.example` актуален.
- Любое неочевидное решение — строка в DECISIONS.md (что, почему, какие альтернативы).

## 7. Финальная самопроверка и отчёт (Definition of Done)

Прогони НАСТОЯЩИЙ пайплайн: МФТИ, 200–300 авторов, их работы, профили, экспорт. Затем сгенерируй `docs/REPORT.md`:

- Сколько авторов получено / сколько прошло эвристику НР / сколько с h_index, с ≥1 abstract, со «свежей» публикацией; медианы works_count и h_index.
- 5 примеров profile_text (глазами: похоже на осмысленный профиль учёного? отметь проблемы).
- Топ-15 тем по кандидатам в НР.
- Проблемы данных: дубли, пустые поля, мусорные аффилиации — и что с ними делать в SFR-1.
- Время прогона, число запросов к API, размер кэша.

Чеклист DoD (все пункты — в конец REPORT.md, отметь честно):
- [ ] `make setup && make lint && make typecheck && make test` — зелёные с нуля на чистом клоне
- [ ] CI-workflow валиден (actionlint или ручная проверка синтаксиса)
- [ ] Реальный прогон 200–300 авторов МФТИ прошёл; `profiles.jsonl` существует и валиден (каждая строка парсится, profile_text 300–1500 симв. у ≥80% профилей)
- [ ] Повторный запуск ингеста не создаёт дублей и почти не ходит в сеть (кэш)
- [ ] README: quickstart работает как написано
- [ ] DECISIONS.md и NEXT.md заполнены (NEXT.md: план SFR-1 — мини-тест embedding-моделей на этих профилях, 3 модели × 20 запросов)

Если что-то из DoD не дотянул — не маскируй: опиши в REPORT.md, что не готово и почему.
