.PHONY: setup lint typecheck test test-integration test-slow etl report format unhide \
	index eval eval-sfr1 eval-report index-sfr2 eval-sfr2 api docker-build docker-up docker-down bench \
	export-cards web-setup web-dev web-lint web-typecheck web-test web-build web-e2e \
	deploy-local deploy-local-down audit \
	catalog-sfr5 index-sfr5 eval-sfr5 export-sfr5 board-sync board-sync-dry

# macOS: uv marks .venv files with the UF_HIDDEN flag, and CPython >= 3.12.13 skips
# hidden .pth files, which silently breaks editable workspace imports.
# Clearing the flag is a no-op on Linux/CI (chflags is absent). See docs/DECISIONS.md.
unhide:
	@command -v chflags >/dev/null 2>&1 && chflags -R nohidden .venv 2>/dev/null || true

setup:
	uv sync --all-packages
	@$(MAKE) unhide
	uv run pre-commit install

lint: unhide
	uv run ruff check .
	uv run ruff format --check .

format: unhide
	uv run ruff check --fix .
	uv run ruff format .

typecheck: unhide
	uv run mypy packages/sfr-core/src/sfr_core packages/sfr-etl/src/sfr_etl \
		packages/sfr-match/src/sfr_match apps/api/src/sfr_api

test: unhide
	uv run pytest -m "not integration and not slow"

test-integration: unhide
	uv run pytest -m integration --no-cov

# Runs a real embedding model. Kept out of `make test` (slow, downloads weights) and
# out of the same process as the rest of the suite: torch and faiss must not both be
# active in one interpreter on macOS (see packages/sfr-match/src/sfr_match/runtime.py).
test-slow: unhide
	uv run pytest -m slow --no-cov

# Full ETL pipeline. Requires an institution resolved beforehand:
#   uv run sfr institutions resolve "Moscow Institute of Physics and Technology"
etl: unhide
	uv run sfr etl authors --max 300
	uv run sfr etl works --since-years 5 --per-author 25
	uv run sfr etl build-profiles
	uv run sfr export jsonl --out data/exports/profiles.jsonl

report: unhide
	uv run sfr report

# ---------------------------------------------------------------------------
# SFR-1: embedding model mini-test
# ---------------------------------------------------------------------------
MATCH_MODELS := bm25 minilm e5-base mpnet frida

# All variants of §3 SPEC_SFR1, raw and cleaned profile_text.
index: unhide
	@for m in $(MATCH_MODELS); do \
		uv run sfr-match index -m $$m --no-clean || exit 1; \
		uv run sfr-match index -m $$m --clean || exit 1; \
	done

# Full SFR-1 reproduction. NOT the default target any more: it ends in
# `sfr-match report`, which rewrites the frozen docs/SFR1_REPORT.md — and the
# judging pool has grown since, so nDCG there would move retroactively.
eval-sfr1: index
	uv run sfr-match eval --models $(shell echo $(MATCH_MODELS) | tr ' ' ',') --no-clean
	uv run sfr-match eval --models $(shell echo $(MATCH_MODELS) | tr ' ' ',') --clean
	uv run sfr-match pool
	uv run sfr-match report

# Report only (rankings and judgments already on disk).
eval-report: unhide
	uv run sfr-match report-sfr2

# ---------------------------------------------------------------------------
# SFR-2: search API over the two-university corpus
# ---------------------------------------------------------------------------
SFR2_PROFILES := data/exports/profiles_mipt_msu.jsonl
SFR2_INDEX_ROOT := data/indexes_sfr2
SFR2_MODELS := frida mpnet
SFR2_COMPOSITIONS := full topics topics_titles

# Six indexes: two models x three profile_text compositions (SPEC_SFR2 §5).
# Cleaning is on for all of them, so the comparison is internally consistent.
index-sfr2: unhide
	@for m in $(SFR2_MODELS); do \
		for c in $(SFR2_COMPOSITIONS); do \
			uv run sfr-match index -m $$m --clean --compose $$c \
				--profiles $(SFR2_PROFILES) --index-root $(SFR2_INDEX_ROOT) || exit 1; \
		done; \
	done

SFR2_RUNS := data/eval/runs_sfr2
SFR2_OOD_RUNS := data/eval/runs_ood

# Full SFR-2 reproduction: every composition on the golden set, the OOD set for
# threshold calibration, then the report. Index building is a separate target
# (hours of embedding); this one only needs the indexes to exist.
#
# ВНИМАНИЕ (SFR-5): последний шаг перезаписывает docs/SFR2_REPORT.md, а входные
# наборы с тех пор пересмотрены — посторонние 17 → 19, а в golden set четыре
# запроса (q27-q30) перемечены из out-of-domain в edge/in-domain. Поэтому в
# отчёте задним числом сдвинутся таблица калибровки, nDCG, строка состава
# наборов — и Success@k тоже: compute_metrics считает по запросам in-domain, а
# их теперь 24 вместо 22. Проверка «код цел, изменились данные» — прогон с
# исходной разметкой (git stash push packages/sfr-match/eval/queries.jsonl):
# на ней Success@1/@3/@5 и MRR воспроизводятся байт в байт.
# Разбор прогона 06.09 — docs/SFR5_REPORT.md §8. После прогона отчёт возвращать:
#   git checkout docs/SFR2_REPORT.md
eval: eval-sfr2

eval-sfr2: unhide
	@for c in $(SFR2_COMPOSITIONS); do \
		uv run sfr-match eval --models frida,mpnet --clean --compose $$c \
			--index-root $(SFR2_INDEX_ROOT) --runs-dir $(SFR2_RUNS) || exit 1; \
	done
	uv run sfr-match eval --models frida,mpnet --clean --compose full --queries ood \
		--index-root $(SFR2_INDEX_ROOT) --runs-dir $(SFR2_OOD_RUNS)
	uv run sfr-match pool --runs-dir $(SFR2_RUNS) --index-root $(SFR2_INDEX_ROOT) \
		--out data/eval/pool_sfr2.jsonl
	uv run sfr-match pool --runs-dir $(SFR2_OOD_RUNS) --queries ood \
		--index-root $(SFR2_INDEX_ROOT) --out data/eval/pool_ood.jsonl
	uv run sfr-match calibrate --runs-dir $(SFR2_RUNS) --ood-runs-dir $(SFR2_OOD_RUNS)
	uv run sfr-match report-sfr2

# Card enrichment for the API (SFR-3): citations + top works, from the local DB.
# Псевдоним export-sfr5: до SFR-5 цель писала в data/exports/cards.jsonl, который
# сервис больше не читает, — регенерация «по документации» ничего не меняла.
export-cards: export-sfr5

# Локальный API сервит боевой индекс SFR-5 (12 вузов); переопределяется
# переменной окружения SFR_API_INDEX_ROOT — например, на data/indexes_sfr2,
# чтобы поднять API на корпусе SFR-2.
api: unhide
	SFR_API_INDEX_ROOT=$${SFR_API_INDEX_ROOT:-data/indexes_sfr5} \
	SFR_API_CARDS_PATH=$${SFR_API_CARDS_PATH:-data/exports/cards_sfr5.jsonl} \
		uv run uvicorn sfr_api.main:app --factory --host 127.0.0.1 --port 8000 \
		--limit-concurrency 8

docker-build:
	docker compose build

# Bind-mounts the host HuggingFace cache so the model is not re-downloaded.
docker-up:
	SFR_HF_CACHE=$$HOME/.cache/huggingface docker compose up -d
	@echo "curl -s localhost:8000/api/health"

docker-down:
	docker compose down

# Resource + latency measurements for the report (SPEC_SFR2 §3).
bench: unhide
	uv run python scripts/bench_api.py --out docs/sfr2_resources.json

# ---------------------------------------------------------------------------
# SFR-5: каталог 12 вузов, стратифицированный отбор, дедупликация, свой индекс.
# Индекс SFR-2 (data/indexes_sfr2) не трогается: на нём стоит воспроизводимость
# SFR-2 (`make eval-sfr2`).
# ---------------------------------------------------------------------------
SFR5_PROFILES := data/exports/profiles_sfr5.jsonl
SFR5_CARDS := data/exports/cards_sfr5.jsonl
SFR5_INDEX_ROOT := data/indexes_sfr5
SFR5_RUNS := data/eval/runs_sfr5
SFR5_OOD_RUNS := data/eval/runs_ood_sfr5

# Пересборка каталога из БД: склейка дублей, профили, экспорты.
# Ингест авторов и работ сюда не входит намеренно: он ходит в сеть и упирается
# в дневной бюджет OpenAlex (docs/DECISIONS.md), команды — в docs/SFR5_REPORT.md.
catalog-sfr5: unhide
	uv run sfr etl backfill-mega
	uv run sfr etl dedup --apply
	uv run sfr etl build-profiles
	$(MAKE) export-sfr5

export-sfr5: unhide
	uv run sfr export jsonl --out $(SFR5_PROFILES)
	uv run sfr export cards --out $(SFR5_CARDS)

# Один индекс: боевая пара frida + full (состав индекса решён в SFR-2).
# Второй шаг обязателен: свежий meta.json приходит без порогов, и без штампа
# сверка сервиса на старте молчит (`thresholds_match: null`). Числа берутся из
# ApiSettings — в Makefile их дублировать нельзя, пороги живут в settings.
index-sfr5: unhide
	uv run sfr-match index -m frida --clean --compose full \
		--profiles $(SFR5_PROFILES) --index-root $(SFR5_INDEX_ROOT)
	SFR_API_INDEX_ROOT=$(SFR5_INDEX_ROOT) uv run python scripts/stamp_thresholds.py

# Регрессия на новом корпусе: golden + OOD, затем пул для судейства.
eval-sfr5: unhide
	uv run sfr-match eval --models frida --clean --compose full \
		--index-root $(SFR5_INDEX_ROOT) --runs-dir $(SFR5_RUNS)
	uv run sfr-match eval --models frida --clean --compose full --queries ood \
		--index-root $(SFR5_INDEX_ROOT) --runs-dir $(SFR5_OOD_RUNS)
	uv run sfr-match pool --runs-dir $(SFR5_RUNS) --index-root $(SFR5_INDEX_ROOT) \
		--out data/eval/pool_sfr5.jsonl
	uv run sfr-match pool --runs-dir $(SFR5_OOD_RUNS) --queries ood \
		--index-root $(SFR5_INDEX_ROOT) --out data/eval/pool_ood_sfr5.jsonl

# ---------------------------------------------------------------------------
# SFR-3: web front (apps/web, Next.js). npm is pinned by package-lock.json.
# ---------------------------------------------------------------------------
web-setup:
	cd apps/web && npm ci

web-dev:
	cd apps/web && npm run dev

web-lint:
	cd apps/web && npm run lint

web-typecheck:
	cd apps/web && npm run typecheck

web-test:
	cd apps/web && npm run test

web-build:
	cd apps/web && npm run build

# Playwright against a live API (`make api` in another terminal). Local only, not in CI.
web-e2e:
	cd apps/web && npm run e2e

# ---------------------------------------------------------------------------
# SFR-4: репетиция боевой компоновки (api + web + proxy) на локальной машине.
# Прокси слушает http://localhost:8080, API наружу не публикуется вовсе.
# e2e против неё: SFR_WEB_URL=http://localhost:8080 make web-e2e
# ---------------------------------------------------------------------------
DEPLOY_COMPOSE := docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.local.yml

deploy-local:
	SFR_HF_CACHE=$$HOME/.cache/huggingface \
	SITE_ADDRESS=http://localhost:8080 \
	NEXT_PUBLIC_SITE_URL=http://localhost:8080 \
	REVALIDATE_SECRET=local-rehearsal \
	$(DEPLOY_COMPOSE) up -d --build
	@# Пересозданный контейнер web теряет рантайм-кэш ISR: без ревалидации
	@# sitemap и лендинг отдают билд-снапшот (собранный без API). На бою этот
	@# шаг — часть процедуры деплоя (deploy/README.md).
	@until curl -sf -o /dev/null http://localhost:8080/; do sleep 1; done
	@curl -s -X POST -H "x-revalidate-secret: local-rehearsal" \
		http://localhost:8080/api/revalidate && echo
	@echo "прокси: http://localhost:8080 · api снаружи недоступен (проверка: docker port sfr-api -> пусто)"

deploy-local-down:
	SITE_ADDRESS=http://localhost:8080 NEXT_PUBLIC_SITE_URL=http://localhost:8080 \
	$(DEPLOY_COMPOSE) down

# ---------------------------------------------------------------------------
# SFR-4b: аудит безопасности (статический анализ + зависимости + секреты).
# Полный список инструментов и политика падения — docs/SFR4b_REPORT.md.
# Питоновские сканеры — из uv-группы security, бинарные (gitleaks, trivy,
# hadolint) — из PATH или из запиненного docker-образа; чего нет — SKIP.
# ---------------------------------------------------------------------------
audit: unhide
	uv run --group security python scripts/audit.py $(AUDIT_ARGS)

# ---------------------------------------------------------------------------
# Доска «SFR — задачи»: поля Status / Priority / Iteration — производные от
# лейблов issues. Правила маппинга — в докстринге scripts/gh_board_sync.py и
# в CLAUDE.md. Идемпотентно: повторный прогон ничего не меняет.
# Нужен scope project у gh (gh auth refresh -s project).
# ---------------------------------------------------------------------------
board-sync: unhide
	uv run python scripts/gh_board_sync.py

board-sync-dry: unhide
	uv run python scripts/gh_board_sync.py --dry-run
