# Search For Research

Сервис кросс-вузового подбора научных руководителей: студент описывает научные
интересы → получает 5–10 релевантных НР (embedding-поиск по их публикациям).
Работает на https://search-for-research.ru. Это указатель; содержание — по ссылкам.

**Куда идти**

- `CLAUDE.md` — правила репозитория: задачи в GitHub Issues, артефакты сессии, команды, жёсткие правила, DoD.
- `docs/README.md` — карта: три места проекта, как читать репозиторий за 5 минут, что где лежит, откуда нельзя брать цифры.
- `docs/DECISIONS.md` — блок «Состояние» (каталог, индекс, пороги, качество, открытая итерация) и сводка действующих решений.
- `docs/product/` — документы стартапа (бриф «Где мы сейчас», спека MVP, история и Q&A, гранты, ресерчи); оглавление — `docs/product/README.md`.
- `docs/reports/` — отчёты итераций; `docs/specs/` — спеки закрытых итераций; `docs/metrics/` — JSON метрик (генерируются).
- `apps/api/README.md` (FastAPI-сервис поиска), `apps/web/README.md` (Next.js), `deploy/README.md` (выкладка на VPS), `packages/sfr-match/eval/README.md` (golden set, судейство, дедупликация).
- Задачи и доска — https://github.com/users/borisboriov/projects/5.

**Старт**

```bash
git clone <repo-url> && cd search-for-research
cp env.example .env             # OPENALEX_MAILTO и OPENALEX_API_KEY
make setup                      # uv sync + pre-commit
make test                       # pytest + coverage
```

**Команды** — цели Makefile (комментарии над целями): `setup` · `lint` · `typecheck` · `test` · `test-integration` · `audit` ·
`api` · `docker-up` / `docker-down` · `web-dev` / `web-build` / `web-e2e` · `catalog-sfr5c` / `index-sfr5c` / `eval-sfr5c` / `metrics-sfr5c` (боевой каталог) ·
`bench` · `deploy-local` · `board-sync` / `issues-audit` · `hooks-test`. Цели `*-sfr5` и `*-sfr5b` заморожены — воспроизводимость прежних отчётов.

**Структура**

```
packages/sfr-core/   # доменное ядро: модели SQLAlchemy, настройки, схемы экспорта
packages/sfr-etl/    # клиент OpenAlex, ингест, отбор авторов (catalog.py), дедупликация (dedup.py), CLI `sfr`
packages/sfr-match/  # индекс, поиск, eval-харнесс, CLI `sfr-match`; eval/ — golden set, рубрика, оценки (в git — это актив)
apps/api/            # FastAPI-сервис поиска: /api/match, /api/supervisors, /api/health
apps/web/            # фронт Next.js (дизайн-система apps/web/design/DESIGN_SYSTEM.md)
deploy/              # боевая компоновка: compose, Caddy, процедуры выкладки
scripts/             # бенчи, метрики, аудит, синхронизация доски
data/                # gitignored: raw-кэш API, SQLite, экспорты, индексы, прогоны eval
docs/                # карта в docs/README.md
```

Требования: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 24 LTS для `apps/web`.
