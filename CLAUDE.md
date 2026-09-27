# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Текущее состояние

Закрыты итерации SFR-0…SFR-6, SFR-4b, SFR-5b, SFR-5c; сервис работает на `https://search-for-research.ru` (выложен 08.09.2026, каталог с потолком на вуз — с 26.09). **Состояние и боевые цифры — только в блоке «Состояние» в начале `docs/DECISIONS.md`** (каталог, индекс, пороги, качество с условиями применимости, открытая итерация) — здесь они не повторяются; сводка действующих решений — там же, ниже блока. Отчёт последней итерации — `docs/reports/SFR5c_REPORT.md`; карта `docs/` и порядок чтения репозитория — `docs/README.md`.

**Спека итерации — единственный источник требований для неё**, всё остальное вне скоупа. Спека открытой итерации лежит в корне репозитория (есть ли открытая — блок «Состояние»); спеки закрытых — в `docs/specs/` (`SPEC_SFR0.md`… `SPEC_SFR5c_catalog_cap.md`, `SPEC_SFR6_design.md`), читать как историю требований, а не как задание. На итерацию в репо остаются спека + отчёт `docs/reports/SFR<N>_REPORT.md`; ревью, снапшоты и промежуточные заметки живут до закрытия итерации и удаляются (находки ревью — issues `from-review`).

**У OpenAlex дневная квота:** анонимно 1 000 запросов, с бесплатным ключом (`OPENALEX_API_KEY`) — 10 000; полный бэкфилл каталога стоит 10 014 запросов. Тяжёлые многочасовые процессы (индекс) — `nohup` вне фоновых задач харнесса (`docs/DECISIONS.md` 18.09).

**Режим автономный**: вопросы задавать некому. Принимай разумные решения сам и фиксируй каждое неочевидное в `docs/DECISIONS.md` (что, почему, какие альтернативы).

## Задачи — в GitHub Issues

Задачи проекта живут в issues этого репозитория и на доске «SFR — задачи»
(https://github.com/users/borisboriov/projects/5), а не в markdown (с 12.09.2026;
отчёт переноса — `docs/reports/GH_MIGRATION_REPORT.md`). Репозиторий приватный.

**Лейблы.** У каждого issue ровно один лейбл «кто» и один-два «область», плюс приоритет:

| Кто | Смысл |
|---|---|
| `agent` | делает автономная сессия Claude Code по спеке итерации (длинная, запускается когда удобно Борису — днём или ночью) |
| `human` | нужны руки или решение Бориса (купить, проверить глазами, договориться) |
| `sveta` | задача Светы |
| `decision` | открытое решение — сначала решить, потом появятся задачи |

Область: `code` (поиск, API, фронт, деплой, данные) · `docs` (паспорт, дек, бриф, Диск, спека MVP) ·
`product` (продуктовые решения, пилот, тестеры, юзер-тесты) · `grant` · `design` · `legal` (152-ФЗ,
документы сайта, обезличивание). Приоритет: `P0` / `P1` / `P2`. Служебные: `blocked` (ждёт внешнего
события или другой задачи), `from-review` (находка ревью итерации).

**Milestones — вехи курса** (`docs/product/course_plan_NIR3-4.pdf`, трек «Стартап»); один на issue или ни одного (бэклог):
Пилот 5 тестеров — 30.09.2026 · Промежуточная презентация НИР 3 — 15.11.2026 *(окно «октябрь — ноябрь», дата-допущение)* ·
Аттестация НИР 3 — 31.12.2026 · Пилот зима 2026/27 — 28.02.2027 · Предзащита и защита ВКР — 30.06.2027 · Грант ФСИ VIII — без даты.

**Именование итераций.** Код `SFR-<N>` — ключ (ветка, коммиты, спека, отчёт), плюс слово: на доске `SFR-7 · Ранжирование`,
спека `SPEC_SFR7_ranking.md`, отчёт `docs/reports/SFR7_REPORT.md`. Закрытые: SFR-0 монорепа и ETL · SFR-1 выбор модели (FRIDA) ·
SFR-2 API и пороги · SFR-3 фронт · SFR-4 деплой · SFR-4b аудит в CI · SFR-5 каталог 12 вузов · SFR-5b каталог без квоты (эксперимент для #90) · SFR-5c каталог с потолком на вуз (выложен 26.09) · SFR-6 «Академичная свежесть» (дизайн B).

**Правила для агента:**

- Перед началом работы: `gh issue list --label agent --milestone "<текущий>" --state open` — это список работ итерации. **Спека уточняет «как», issues — «что».**
- Коммит, закрывающий задачу, содержит `Closes #N` в теле; вручную issue без коммита не закрывать.
- Новая находка → `gh issue create` (`agent` + область + приоритет; требует человека — `human`), но сначала `gh issue list --search`, чтобы не плодить дубли. Связи между issues (часть/блокирует) ставить сразу комментарием или sub-issue.
- Находки ревью (`/review-iteration`) → issues с лейблом `from-review`.
- **Ссылки в issue.** Файл репозитория, о котором идёт задача (код, отчёт, спека, eval-файл), — всегда ссылкой на `blob/main` без номера строки: [`docs/reports/SFR5_REPORT.md`](https://github.com/borisboriov/search-for-research/blob/main/docs/reports/SFR5_REPORT.md) §5 — параграф словами, потому что строки уезжают. Permalink по SHA — только если важна конкретная строка на конкретной версии. Удалённые файлы (`docs/NEXT.md`, `TODO_BORIS.md`, TODO-файлы папки) — не ссылать: в «Откуда» остаётся имя файла текстом и дословная цитата, история — `git log --all -- <путь>`. Продуктовые документы лежат в `docs/product/` (бриф, спека MVP, ресерчи, план курса) — на них тоже ссылка на `blob/main`. Бинарники папки документов (паспорт xlsx, дек pptx, скрины) — именем файла без пути.
- Агент **не меняет** milestones, лейблы `sveta` и `decision` и не удаляет issues.
- **Ветки, PR, merge и push.** Агент работает в ветке (`sfr-<N>` для итерации, имя по теме для мини-сессии), делает коммиты, **сам пушит свою ветку** (`git push -u origin <ветка>`, с 27.09.2026) и открывает PR (`gh pr create`, текст — по правилам ниже). Push в `main`, `--force`, удаление веток, merge PR и выкладка на VPS — только Борис: хук `.claude/hooks/block-push.sh` отклоняет эти формы (`gh pr merge`, push в `main`/`master`, force/delete/all/tags, push без явной ветки из `main`) и пропускает push своей ветки; тесты — `make hooks-test`.
- «Требует человека» = issue `human` (и `decision` для нерешённого). Закрытые issues не удалять: внешнему агенту нужна история.

**Правила для Бориса и Светы:** доска — главный экран; замечания и результаты — комментарием в issue, а не файлом;
закрыть = Status `Done` или Close; новая задача — New issue с лейблами «кто» + «область» + приоритет; Status `Waiting` —
ждёт человека или внешнего события. Приоритет дублируется лейблом `P0`–`P2`, чтобы его видели и через API issues.

```bash
gh issue list --label human --state open          # что на Борисе
gh issue list --label agent --milestone "Пилот 5 тестеров" --state open
gh issue list --search "дедуп"                    # нет ли уже такого
gh issue create --title "…" --label "agent,code,P2"
gh issue comment 42 --body "…"
```

**Поля доски — производные от лейблов: `make board-sync`.** Руками поля Status / Priority / Iteration
не проставляются — их выводит из issues `scripts/gh_board_sync.py` (правила целиком — в его докстринге):
Priority ← лейбл `P0`/`P1`/`P2`; Status: issue закрыт → `Done`, `In Progress` на доске → не трогать
(это руками Бориса), лейбл `blocked` → `Waiting`, остальные открытые → `Todo`; Iteration → текущая
итерация только для `agent` с milestone текущей вехи. Скрипт идемпотентен и ничего не сбрасывает:
поле, для которого правила молчат, остаётся как есть. Issues репозитория, которых на доске нет,
добавляет сам. Прогон — после любого треда, где заводились или закрывались задачи:

```bash
make board-sync-dry   # план, ничего не меняет
make board-sync       # применить
```

Нужен scope `project` у `gh` (`gh auth refresh -s project`). Встроенные автоматизации доски
(«Item added → Todo», «Item closed → Done») включены 14.09 в её настройках — через CLI они не
ставятся; `make board-sync` остаётся для всего остального и для уже лежащего на доске.

**Гигиена и интерактивная работа.** `make issues-audit` (`scripts/gh_issues_audit.py`) механически
проверяет таксономию: лейблы «кто»/«область»/приоритет, открытые `agent` без milestone, задачи без
движения, кандидаты в дубли, чего нет на доске. Ничего не чинит — печатает отчёт. Процедуры
(завести задачу, триаж, дайджест «что на мне», закрытие итерации) — команда **`/issues`**
(`.claude/commands/issues.md`); правила таксономии остаются здесь, команда на них ссылается.

**Конфигурация Claude Code — в git** (с 26.09.2026): `.claude/settings.json` (режим `auto`, allow/deny,
Stop-хук `.claude/hooks/review-reminder.sh`, PreToolUse-хук `.claude/hooks/block-push.sh`), субагенты `.claude/agents/` (`sfr-reviewer` — независимое
ревью итерации, `sfr-judge` — слепое судейство пар по рубрике `packages/sfr-match/eval/JUDGE_RUBRIC.md`),
команды `.claude/commands/` (`/issues`, `/review-iteration`). Личное — только `.claude/settings.local.json`
(исключён через `.claude/.gitignore`). **Граница — только хук `block-push.sh`** (#129, DECISIONS 27.09):
он отклоняет push в `main`, force/delete и `gh pr merge` по разобранным аргументам и пропускает push своей ветки (с 27.09.2026), тесты — `make hooks-test`; **`make docs-check`** (`scripts/docs_check.py`, в CI) — согласованность живых документов: пути, старые адреса, блок «Состояние» против брифа, `meta.json` индекса и `ApiSettings`; `make docs-check-live` — плюс боевой `/api/health`;
`allow`/`deny` в settings — гигиена и подсказка, а не защита.

## Что это за проект

Search For Research — сервис кросс-вузового подбора научных руководителей: студент вводит описание интересов → получает 5–10 релевантных НР (embedding-поиск по их публикациям).

Целевая архитектура целиком: ETL (офлайн) → PostgreSQL → FAISS + sentence-transformers → FastAPI → Next.js.
Сделано: ETL (`packages/sfr-etl`, включая стратифицированный отбор
`catalog.py` и дедупликацию `dedup.py`), поиск и оценка (`packages/sfr-match`), API
(`apps/api`, FastAPI + Docker), фронт (`apps/web`, Next.js — см. его README, `apps/web/design/DESIGN_SYSTEM.md` v2.1
и `DESIGN_HANDOFF.md`; макеты направления B лежат в папке документов
(`~/Desktop/Search for Research`/`02_research/2026-09_дизайн_референсы/directions_2026-09-12/`) и в репо не
копируются, `design/mockups/*` — история v1), боевая компоновка
(`deploy/`, SFR-4 — выложена на VPS 08.09). Осталось:
переезд с файлового индекса на PostgreSQL/pgvector — только когда корпус
перерастёт десятки тысяч профилей, на текущем каталоге `IndexFlatIP` ещё достаточен.

## Команды

Стек: **uv** (workspace + lock), Python 3.12+, ruff, mypy, pytest.

```bash
make setup       # uv sync, установка pre-commit
make lint        # ruff check + ruff format --check
make typecheck   # mypy (strict для sfr-core, basic допустим для sfr-etl)
make test        # pytest + coverage (порог ≥80% зашит в конфиг)
make etl         # прогон пайплайна
make report      # генерация docs/reports/REPORT.md
```

Точечный запуск тестов:
```bash
uv run pytest packages/sfr-etl/tests/test_abstracts.py::test_inverted_index_empty -q
uv run pytest -m integration     # контрактный смоук по живому OpenAlex; в CI НЕ гоняется
uv run pytest -m "not integration"
```

Итерация SFR-2 добавила:

```bash
make index-sfr2  # шесть индексов: frida/mpnet x три состава profile_text
make eval        # = eval-sfr2, воспроизведение всех цифр docs/reports/SFR2_REPORT.md
make api         # uvicorn на localhost:8000
make docker-up   # то же в контейнере (индекс монтируется, модель — из HF-кэша)
make bench       # замер ресурсов и латентности → docs/metrics/sfr2_resources.json
```

Итерация SFR-3 добавила:

```bash
make export-sfr5c   # data/exports/cards_sfr5c.jsonl — обогащение карточек для API
make web-setup      # npm ci в apps/web
make web-dev / web-lint / web-typecheck / web-test / web-build
make web-e2e        # Playwright против живого API; скриншоты в e2e/screenshots
```

Итерация SFR-4 добавила:

```bash
make deploy-local       # репетиция боевой компоновки: api+web+proxy на localhost:8080
                        # (после up сам делает пост-деплойную ревалидацию ISR)
make deploy-local-down  # остановить её
SFR_WEB_URL=http://localhost:8080 make web-e2e   # e2e против компоновки
uv run python scripts/bench_sfr4.py              # перемер §3 + проверки защиты
```

Итерация SFR-5 добавила (боевые цели — `*-sfr5c`, блок SFR-5 заморожен: его
цели перезапишут артефакты, на которых стоит воспроизводимость SFR-5):

```bash
uv run sfr etl authors --institution <id> --strategy stratified --quota 500
uv run sfr etl works --institution <id>   # по вузам: сбой стоит одного вуза
make catalog-sfr5c  # backfill-mega + dedup --apply + build-profiles + экспорты
uv run sfr etl dedup                       # по умолчанию --dry-run (#10); пишет review-файл
uv run sfr etl unmerge A5… [--apply]       # расклеить ложную склейку из raw и кэша (#108)
make index-sfr5c    # индекс frida_clean по profiles_sfr5c.jsonl + штамп порогов
make eval-sfr5c     # golden + OOD + external, затем судейские пулы
make metrics-sfr5c  # docs/metrics/sfr5c_metrics.json и таблица трёх точек
make review-sfr5c   # выборка судейских оценок на проверку человеком
uv run python scripts/contacts_experiment.py   # §5, только измерение
```

**Решения человека о склейках** — `packages/sfr-match/eval/dedup_decisions.jsonl`
(`same` склеивает поверх блокеров, `different` запрещает навсегда); без файла
`dedup --apply` останавливается. **Судейство** — субагент `sfr-judge` по рубрике
`packages/sfr-match/eval/JUDGE_RUBRIC.md`; цифры качества наружу берутся только
со слепого пула (`sfr-match pool --blind`, `make metrics-deploy-sfr5c`).

**Порядок для ингеста работ:** сначала `scripts/warm_works_cache.py`
(греет дисковый кэш в несколько потоков, останавливается на 429), затем
`sfr etl works --only-missing` (пишет в БД по кэшу, без сети). Запускать
`sfr etl works` в лоб на всём каталоге не нужно: он однопоточный и тратит
по два запроса квоты на каждого уже загруженного автора.

Итерация SFR-4b добавила:

```bash
make audit                              # семь сканеров одной командой
make audit AUDIT_ARGS="--no-images"     # как в CI (образы там не собираются)
bash security/semgrep/fetch-rules.sh    # обновить вендоренные правила semgrep
```

Политика падения, allowlist и базовая линия — `docs/reports/SFR4b_REPORT.md`. Питоновские
сканеры — в uv-группе `security` (не в `default-groups`); бинарные берутся из
PATH или из запиненного docker-образа.

Боевой контур — каталог `deploy/` (compose, Caddyfile с rate limiting,
sync-artifacts.sh, README с процедурами); гайд пилота — `docs/PILOT_TEST_GUIDE.md`.
Пороги уверенности живут в настройках API, отдаются в `/health` и штампуются
в `meta.json` индекса шагом `make index-sfr5c` (`scripts/stamp_thresholds.py`,
числа берутся из `ApiSettings`); действующие значения — блок «Состояние»
`docs/DECISIONS.md`, обоснование — §13 отчёта выложенного индекса, рецепт `weak`/`high` — в коде
(`threshold_hints` в `scripts/analyze_sfr5.py`). Фронт чисел не знает, менять
только в `ApiSettings` — и одновременно с индексом и `cards`.

CLI пайплайна (typer, точка входа `sfr`):
```bash
uv run sfr institutions resolve "Moscow Institute of Physics and Technology"
uv run sfr etl authors --institution <id> --max 300
uv run sfr etl works --since-years 5 --per-author 25
uv run sfr etl build-profiles
uv run sfr export jsonl --out data/exports/profiles.jsonl
uv run sfr report
```

CI (GitHub Actions): `ci.yml` — job `checks` (`make lint && make typecheck && make test`) и job `web` (lint + typecheck + unit + build; сборка обязана проходить без живого API); `security.yml` — job `audit` (`make audit`) на push, PR и еженедельный cron, без секретов и платных возможностей GitHub.

## Архитектура

uv-workspace монорепа из двух пакетов:

- **`packages/sfr-core/`** (`src/sfr_core/`) — доменное ядро: модели SQLAlchemy 2.x, `pydantic-settings` конфиг, Pydantic-схемы экспорта. Не знает про HTTP и OpenAlex.
- **`packages/sfr-etl/`** (`src/sfr_etl/`) — клиент OpenAlex (httpx + tenacity), ингест, сборка профилей, typer-CLI. Зависит от core, не наоборот.

Поток данных: **OpenAlex API → дисковый кэш `data/raw/` → SQLAlchemy (SQLite-файл в `data/`) → SupervisorProfile → `data/exports/profiles.jsonl`** — этот JSONL и есть вход для SFR-1 (embeddings). `data/` — gitignored.

БД: SQLite по умолчанию, но **в проде PostgreSQL — ни одной SQLite-специфичной фичи** в моделях и типах. Миграции — alembic.

### Домен

Сущности: `Institution`, `Author`, `Work`, `AuthorTopic`, `SupervisorProfile`. Детали полей — §3 `docs/specs/SPEC_SFR0.md`.

Главный артефакт — **`profile_text`**: связный текст 300–1500 символов (имя, аффилиация, ключевые темы, названия и фрагменты аннотаций 5–10 свежих/цитируемых работ). Русский/английский — как в источнике, **не переводить**. Именно его качество определяет качество будущего поиска.

Эвристика `is_supervisor_candidate`: `works_count ≥ 10` И публикация за последние 3 года И `h_index ≥ 5`. **Пороги — в settings, не в коде**; отсеянных авторов не удалять, хранить с флагом `false` (пороги будут крутиться).

## Жёсткие правила (нарушение = переделка)

- **Сверяйся с реальностью, а не с памятью.** Перед использованием полей OpenAlex сделай пробный запрос и посмотри фактический ответ. Разошлось со спекой SFR-0 — адаптируйся и запиши в `DECISIONS.md`.
- **ID вуза не хардкодить** нигде в коде — только через `sfr institutions resolve` в конфиг/БД.
- `mailto` (polite pool) передаётся **всегда**; пустой env — понятная ошибка при старте, а не молчаливый запрос без него.
- Rate limit ≤10 rps, уважать заголовки, ретраи с экспоненциальным бэкоффом на 429/5xx.
- Кэш raw-ответов на диске (ключ = хэш URL+params); флаг `--refresh` для сброса. Повторный прогон почти не ходит в сеть.
- Ингест идемпотентен: upsert по `openalex_id`, дублей не плодит.
- eLibrary/РИНЦ и любой скрейпинг сайтов — **вне скоупа**.
- Секреты только через env (`OPENALEX_MAILTO`, `SFR_DB_URL`); `.env` в gitignore, пример `env.example` (без точки, в git) держать актуальным.
- Коммиты маленькие, conventional (`feat:`, `test:`, `chore:`), каждый — как будто идёт в PR.
- Тесты — обязательная часть работы, не «если успеешь». Обязательный минимум перечислен в §5 `docs/specs/SPEC_SFR0.md`.

## Definition of Done

**Общее для всех итераций (с SFR-4b):** перед финальным отчётом сессии обязателен зелёный `make audit AUDIT_ARGS="--no-images --strict"` (тот же режим, что CI) — результат одной строкой в DoD-чеклист отчёта. Красный аудит = итерация не закрыта; находки с фиксом чинятся в той же сессии, без фикса — по правилам `docs/reports/SFR4b_REPORT.md`.

DoD не считается закрытым без **настоящего прогона** (МФТИ, 200–300 авторов) и сгенерированного `docs/reports/REPORT.md` со статистикой, 5 примерами `profile_text`, топ-15 тем и разбором проблем данных. Полный чеклист — §7 `docs/specs/SPEC_SFR0.md`.
**Недотянутое не маскировать** — писать в REPORT.md, что не готово и почему.

## Внешний контекст и `docs/product/`

Текстовые документы стартапа с 13.09.2026 живут в репозитории — `docs/product/` (оглавление в `docs/product/README.md`): `brief.md` (бриф, «Где мы сейчас» — входная точка любого треда), `mvp_spec.md` (живой план продукта), `brief_history_qa.md`, `market_stretch_map_*.md`, `research/*`, `course_plan_NIR3-4.pdf`, трекер грантов. Это единственные копии (зеркал в проекте Claude нет с 27.09.2026). **Агент в автономной сессии их не правит** — это документы Бориса и продуктового треда; агент ссылается на них из issues и отчётов, а изменения предлагает разделом «Правки паспорта» в отчёте + issue `human` `docs` (ниже). Папка документов (`~/Desktop/Search for Research`; репозиторий в ней не лежит с 26.09.2026 — он в `~/Projects/search-for-research`, вне iCloud) — бинарники: **паспорт `01_core/Паспорт_Search_For_Research.xlsx` — единственный источник истины по продуктовым цифрам**, дек, обоснование TAM/SAM/SOM, скрины ресерчей, CustDev (персональные данные — наружу не выносить), архив. В коде и отчётах продуктовых цифр и формулировок не заводить; боевые цифры каталога и качества — только блок «Состояние» `docs/DECISIONS.md` и бриф «Где мы сейчас». Правила папки — её `CLAUDE.md`; где что лежит (три места) — `docs/README.md`.

## Артефакты сессии — это интерфейс, а не дневник

Борис ведёт работу над паспортом, спеками и планом следующих этапов **через отдельного агента** (продуктовый тред), который читает артефакты этого репозитория. Отчёты, записи в `DECISIONS.md` и тексты PR — не записки для себя, а входные данные для другой системы. Из этого следуют жёсткие требования.

**Раскладка `docs/` (с 27.09.2026, карта — `docs/README.md`):** отчёты итераций —
`docs/reports/` (`SFR<N>_REPORT.md`, `*_notes.md`, `REPORT.md`), JSON метрик —
`docs/metrics/` (генерируются скриптами и целями Makefile — руками не править; **больше не переносим**),
спеки закрытых итераций — `docs/specs/`, документы стартапа — `docs/product/`;
в корне `docs/` — только `DECISIONS.md`, `SESSIONS.md` (заморожен 27.09.2026 — история), `PILOT_TEST_GUIDE.md` и
`README.md`. Временный отчёт ревью — `docs/reports/REVIEW_<итерация>.md`, в git не идёт.

**Каждая значимая сессия оставляет три вещи** (`docs/SESSIONS.md` с 27.09.2026 не ведётся — что сделано, видно по отчёту, PR и `Closes #N`):

1. **Отчёт с цифрами** (`docs/reports/SFR<N>_REPORT.md`; мини-сессия — раздел в отчёте итерации или свой `*_REPORT.md`). Начинается с **§0 «Резюме для человека»** — не больше экрана, пишется последним и переписывается при каждом дописывании отчёта; дальше — измеренные результаты, честный DoD-чеклист, раздел «Независимое ревью» (его ищет Stop-хук `review-reminder.sh`) и, если итерация дала цифры или выводы для паспорта, раздел **«Правки паспорта»** (ниже). **Недотянутое не маскировать.**
2. **Записи в `docs/DECISIONS.md`** — каждое неочевидное решение (дата — что — почему — альтернативы) и уроки сессии, если они есть (одной записью, только существенное: архитектура, продуктовые решения, аргументы; операционный шум не идёт). При закрытии итерации или выкладке — обновить **блок «Состояние»** в начале файла (каталог, индекс, пороги, качество с условиями, открытая итерация). Отдельный журнал «как шла сессия» не ведётся.
3. **Текст PR** — что сделано, ссылки на отчёт и issues; **промпт мини-сессии** (если сессия шла не по спеке) — целиком в теле PR, раздел «Промпт сессии», а не файлом в папке документов.

**Правки паспорта** (вместо файлов-предложений `docs/product/edits/`, отменённых 27.09.2026):

- Раздел «Правки паспорта» в отчёте — правка **по ячейкам**: лист, координата, «было» → «стало». Не «надо обновить модель», а `лист «5. БФТ», D22: было … стало …`.
- Там же — **оговорки**: на каких данных цифра получена и как её корректно формулировать в защите (цифра без условий применения — ловушка, а не результат), и **цепочка синхронизации** паспорт → дек → обоснование → бриф → Google Drive (автосинхронизации нет).
- Плюс **issue `human` `docs` «внести правку в паспорт: …»** со ссылкой на раздел отчёта (`blob/main`, параграф словами) — единственный адрес правки: её статус живёт в issue (комментарий «внесено дд.мм», закрытие), а не в файлах. Сам паспорт, дек и файлы `01_core` агент **не редактирует**; `docs/product/` — тоже.

**Порядок чтения репозитория** (для ревьюера и продуктового треда) и ловушки цифр — `docs/README.md`; если меняешь структуру артефактов — обнови эту карту и `CLAUDE.md` папки документов.

**То, что требуется от человека, — issues с лейблом `human`** (и `decision` для нерешённого): что блокирует следующий этап и какие решения за Борисом. Закрытые issues не удалять: внешнему агенту нужна история, а не только текущее состояние.
