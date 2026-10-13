.PHONY: setup lint typecheck test test-integration test-slow etl report format unhide \
	index eval eval-sfr1 eval-report index-sfr2 eval-sfr2 api docker-build docker-up docker-down bench \
	export-cards web-setup web-dev web-lint web-typecheck web-test web-build web-e2e \
	deploy-local deploy-local-down audit \
	catalog-sfr5 index-sfr5 eval-sfr5 export-sfr5 board-sync board-sync-dry issues-audit \
	catalog-sfr5b export-sfr5b index-sfr5b eval-sfr5b \
	catalog-sfr5c export-sfr5c index-sfr5c eval-sfr5c metrics-sfr5c review-sfr5c \
	metrics-deploy-sfr5c review-deploy-sfr5c pool-deploy-sfr5c \
	pool-base-blind-sfr5c metrics-base-blind-sfr5c ood19-sfr5c hooks-test stamp-data-date-sfr5c

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
		packages/sfr-match/src/sfr_match apps/api/src/sfr_api scripts enrichment/src \
		enrichment/research/legacy enrichment/tests enrichment/research/inventory.py

test: unhide
	uv run python -m unittest discover -s scripts -p 'test_*.py'
	uv run python enrichment/tests/run_offline.py
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
# `sfr-match report`, which rewrites the frozen docs/reports/SFR1_REPORT.md — and the
# judging pool has grown since, so nDCG there would move retroactively.
# Замороженные отчёты SFR-1 и SFR-2 (#8): штатные цели пишут пересчёт в
# data/eval/*.check.md и печатают, совпал ли он с отчётом в git (полный diff —
# data/eval/*.diff). Перезаписать сам отчёт — только явно: ALLOW_OVERWRITE=1.
ifeq ($(ALLOW_OVERWRITE),1)
SFR1_REPORT_OUT := docs/reports/SFR1_REPORT.md
SFR2_REPORT_OUT := docs/reports/SFR2_REPORT.md
else
SFR1_REPORT_OUT := data/eval/SFR1_REPORT.check.md
SFR2_REPORT_OUT := data/eval/SFR2_REPORT.check.md
endif
# $(1) — замороженный отчёт, $(2) — пересчёт, $(3) — файл diff.
define compare_frozen
	@if [ "$(ALLOW_OVERWRITE)" != 1 ]; then \
		if diff -u $(1) $(2) > $(3); then echo "$(1): пересчёт совпадает с отчётом в git"; \
		else echo "$(1): пересчёт расходится с отчётом в git — $$(grep -c '^[-+][^-+]' $(3)) строк, diff в $(3); отчёт не тронут"; fi; \
	fi
endef

# Снапшот review-выборки в eval/ (#143): доказательство, которое цель
# пересчитывает в data/eval/review. Расхождение — ошибка цели: пересчёт в
# gitignored data/ не виден в `git status`, поэтому его ловит код возврата.
# Снапшот цель не обновляет никогда, в том числе при ALLOW_OVERWRITE=1 —
# обновление доказательства — осознанное копирование с записью в отчёт.
define compare_snapshot
	@if [ "$(ALLOW_OVERWRITE)" = 1 ]; then \
		echo "$(1): ALLOW_OVERWRITE=1 снапшот не обновляет — копировать $(2) руками, с записью в отчёт"; fi
	@if diff -u $(1) $(2) > $(3); then echo "$(1): пересчёт совпадает со снапшотом в git"; \
	else echo "$(1): пересчёт расходится со снапшотом в git — diff в $(3); снапшот не тронут" >&2; exit 1; fi
endef

eval-sfr1: index
	uv run sfr-match eval --models $(shell echo $(MATCH_MODELS) | tr ' ' ',') --no-clean
	uv run sfr-match eval --models $(shell echo $(MATCH_MODELS) | tr ' ' ',') --clean
	uv run sfr-match pool
	uv run sfr-match report --out $(SFR1_REPORT_OUT)
	$(call compare_frozen,docs/reports/SFR1_REPORT.md,$(SFR1_REPORT_OUT),data/eval/SFR1_REPORT.diff)

# Report only (rankings and judgments already on disk).
eval-report: unhide
	uv run sfr-match report-sfr2 --out $(SFR2_REPORT_OUT)
	$(call compare_frozen,docs/reports/SFR2_REPORT.md,$(SFR2_REPORT_OUT),data/eval/SFR2_REPORT.diff)

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
# Последний шаг пишет пересчёт в data/eval/SFR2_REPORT.check.md, а не в
# docs/reports/SFR2_REPORT.md (#8), — и расхождение ожидаемо: входные
# наборы с тех пор пересмотрены — посторонние 17 → 19, а в golden set четыре
# запроса (q27-q30) перемечены из out-of-domain в edge/in-domain. Поэтому в
# отчёте задним числом сдвинутся таблица калибровки, nDCG, строка состава
# наборов — и Success@k тоже: compute_metrics считает по запросам in-domain, а
# их теперь 24 вместо 22. Проверка «код цел, изменились данные» — прогон с
# исходной разметкой (git stash push packages/sfr-match/eval/queries.jsonl):
# на ней Success@1/@3/@5 и MRR воспроизводятся байт в байт.
# Разбор прогона 06.09 — docs/reports/SFR5_REPORT.md §8. Перезаписать сам отчёт —
# `make eval ALLOW_OVERWRITE=1` (затем `git diff` и осознанный коммит).
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
	uv run sfr-match report-sfr2 --out $(SFR2_REPORT_OUT)
	$(call compare_frozen,docs/reports/SFR2_REPORT.md,$(SFR2_REPORT_OUT),data/eval/SFR2_REPORT.diff)

# Card enrichment for the API (SFR-3): citations + top works, from the local DB.
# Псевдоним export-sfr5: до SFR-5 цель писала в data/exports/cards.jsonl, который
# сервис больше не читает, — регенерация «по документации» ничего не меняла.
export-cards: export-sfr5

# Локальный API сервит боевой индекс SFR-5c (12 вузов с потолком на вуз);
# переопределяется переменной окружения SFR_API_INDEX_ROOT — например, на
# data/indexes_sfr2, чтобы поднять API на корпусе SFR-2.
api: unhide
	SFR_API_INDEX_ROOT=$${SFR_API_INDEX_ROOT:-data/indexes_sfr5c} \
	SFR_API_CARDS_PATH=$${SFR_API_CARDS_PATH:-data/exports/cards_sfr5c.jsonl} \
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
	uv run python scripts/bench_api.py --out docs/metrics/sfr2_resources.json

# ---------------------------------------------------------------------------
# SFR-5: каталог 12 вузов квотой — **замороженная** итерация. С выкладки SFR-5c
# (26.09) боевой каталог живёт в `data/sfr.db` с потолком на вуз, а `*_sfr5`
# остаются артефактами измерения SFR-5/5b/5c: `catalog-sfr5`, `export-sfr5` и
# `index-sfr5` перезапишут их каталогом 9 002 — запускать только осознанно.
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
# в дневной бюджет OpenAlex (docs/DECISIONS.md), команды — в docs/reports/SFR5_REPORT.md.
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
# SFR-5b: те же 12 вузов БЕЗ квоты — эксперимент для решения о расширении базы
# НР (#90). Живёт в копии БД (data/sfr5b.db) и в своих путях: боевые data/sfr.db,
# data/indexes_sfr5 и data/exports/*_sfr5.jsonl не трогаются. SFR_DB_URL стоит
# перед каждой командой, которая ходит в БД: env перекрывает .env.
# Ингест (authors без квоты, прогрев кэша работ, works --only-missing) сюда не
# входит по той же причине, что и в SFR-5, — команды в docs/reports/SFR5b_REPORT.md.
# ---------------------------------------------------------------------------
SFR5B_DB_URL := sqlite:///data/sfr5b.db
SFR5B_PROFILES := data/exports/profiles_sfr5b.jsonl
SFR5B_CARDS := data/exports/cards_sfr5b.jsonl
SFR5B_INDEX_ROOT := data/indexes_sfr5b
SFR5B_RUNS := data/eval/runs_sfr5b
SFR5B_OOD_RUNS := data/eval/runs_ood_sfr5b
SFR5B_EXT_RUNS := data/eval/runs_external_sfr5b
# Свой файл выборки, не дефолтный dedup_for_review.md SFR-5. Выборки — в
# gitignored data/eval/review (#143): в git в eval/ лежит только то, что отчёт
# цитирует как доказательство; версия SFR-5b, которую читали по #93, —
# `git show faf626a:packages/sfr-match/eval/dedup_for_review_sfr5b.md`.
SFR5B_DEDUP_REVIEW := data/eval/review/dedup_for_review_sfr5b.md

catalog-sfr5b: unhide
	SFR_DB_URL=$(SFR5B_DB_URL) uv run sfr etl backfill-mega
	SFR_DB_URL=$(SFR5B_DB_URL) uv run sfr etl dedup --apply --review-out $(SFR5B_DEDUP_REVIEW)
	SFR_DB_URL=$(SFR5B_DB_URL) uv run sfr etl build-profiles
	$(MAKE) export-sfr5b

export-sfr5b: unhide
	SFR_DB_URL=$(SFR5B_DB_URL) uv run sfr export jsonl --out $(SFR5B_PROFILES)
	SFR_DB_URL=$(SFR5B_DB_URL) uv run sfr export cards --out $(SFR5B_CARDS)

# Без scripts/stamp_thresholds.py: он штампует пороги боевого индекса из
# ApiSettings, а новому индексу пороги ставятся после калибровки —
# `sfr-match stamp-thresholds --index-dir … --none … --weak … --high …`.
index-sfr5b: unhide
	uv run sfr-match index -m frida --clean --compose full \
		--profiles $(SFR5B_PROFILES) --index-root $(SFR5B_INDEX_ROOT)

eval-sfr5b: unhide
	uv run sfr-match eval --models frida --clean --compose full \
		--index-root $(SFR5B_INDEX_ROOT) --runs-dir $(SFR5B_RUNS)
	uv run sfr-match eval --models frida --clean --compose full --queries ood \
		--index-root $(SFR5B_INDEX_ROOT) --runs-dir $(SFR5B_OOD_RUNS)
	uv run sfr-match eval --models frida --clean --compose full --queries external \
		--index-root $(SFR5B_INDEX_ROOT) --runs-dir $(SFR5B_EXT_RUNS)
	uv run sfr-match pool --runs-dir $(SFR5B_RUNS) --index-root $(SFR5B_INDEX_ROOT) \
		--out data/eval/pool_sfr5b.jsonl
	uv run sfr-match pool --runs-dir $(SFR5B_OOD_RUNS) --queries ood \
		--index-root $(SFR5B_INDEX_ROOT) --out data/eval/pool_ood_sfr5b.jsonl

# ---------------------------------------------------------------------------
# SFR-5c: те же 12 вузов с ПОТОЛКОМ на вуз (МГУ 1 800, СПбГУ 1 200, остальные
# без квоты) — шаг 1 дорожки данных по решению #90 (issue #98).
# **С выкладки 26.09 это боевой контур**, а не эксперимент: каталог переехал в
# `data/sfr.db`, и цели ниже пересобирают то, что стоит в проде. `data/sfr5c.db`
# — снимок **выложенного** каталога 9 002 (совпадает с `sfr.db` на 26.09), а
# не измерения: точка «потолок 9 010» §4–§6 отчёта живёт в архиве `*_9010` и в
# `data/backups/sfr5c_2026-09-26_before_decisions.db` (переменные ниже).
# Снимок сюда не подключён, иначе #99 добавил бы вузы в `sfr.db`, а экспорт
# молча взял бы старый каталог.
# SFR_DB_URL всё равно стоит перед каждой командой, которая ходит в БД: env
# перекрывает .env, но не переживает границу команды.
# Ингест (authors с потолком, works --only-missing) сюда не входит по той же
# причине, что в SFR-5/5b, — команды в docs/reports/SFR5c_REPORT.md.
# ---------------------------------------------------------------------------
SFR5C_DB_URL := sqlite:///data/sfr.db
SFR5C_PROFILES := data/exports/profiles_sfr5c.jsonl
SFR5C_CARDS := data/exports/cards_sfr5c.jsonl
SFR5C_INDEX_ROOT := data/indexes_sfr5c
SFR5C_RUNS := data/eval/runs_sfr5c
SFR5C_OOD_RUNS := data/eval/runs_ood_sfr5c
SFR5C_EXT_RUNS := data/eval/runs_external_sfr5c
# Выборка дедупликации пишется в data/eval/review (#143); в eval/ лежит
# снимок выкладки 9 002 (§13.2 отчёта) — `catalog-sfr5c` его больше не трогает.
SFR5C_DEDUP_REVIEW := data/eval/review/dedup_for_review_sfr5c.md
# Решения человека о склейках (§4 SPEC_SFR5c): актив в git, как judgments.jsonl.
# Абсолютный путь: цель может быть вызвана из подкаталога, а отсутствие файла
# решений под --apply теперь ошибка, а не предупреждение (ревью SFR-5c).
SFR5C_DEDUP_DECISIONS := $(CURDIR)/packages/sfr-match/eval/dedup_decisions.jsonl
SFR5C_EVAL := packages/sfr-match/eval
# Review-выборки пишутся в gitignored data/eval/review (#143). Выборки §7 и
# §13.5, которые отчёт цитирует, лежат в eval/ снимками: цели их не
# перезаписывают, а сверяют с пересчётом (`compare_snapshot`: расхождение — ошибка цели).
SFR5C_REVIEW_DIR := data/eval/review
SFR5C_REVIEW := $(SFR5C_REVIEW_DIR)/judgments_for_review_sfr5c.md
SFR5C_REVIEW_DEPLOY := $(SFR5C_REVIEW_DIR)/judgments_for_review_deploy.md
# Части собранного файла — там же.
SFR5C_DECISIVE := $(SFR5C_REVIEW_DIR)/judgments_decisive_sfr5c.md
SFR5C_SAMPLE := $(SFR5C_REVIEW_DIR)/judgments_sample_sfr5c.md
# Архив измерения «потолок 9 010» (до применения решений о склейках, #98): на
# нём стоят §4, §6 и §7 отчёта.
SFR5C_9010_RUNS := data/eval/runs_sfr5c_9010
SFR5C_9010_OOD_RUNS := data/eval/runs_ood_sfr5c_9010
SFR5C_9010_INDEX_ROOT := data/indexes_sfr5c_9010
SFR5C_9010_PROFILES := data/exports/profiles_sfr5c_9010.jsonl
SFR5C_9010_DB := data/backups/sfr5c_2026-09-26_before_decisions.db
# Набор посторонних, на котором считались §4, §6 и калибровка §13.4, — 19
# запросов до удаления o13/o15 (`a931af0`, DECISIONS 26.09). В действующий
# набор они не возвращаются: архивная редакция достаётся из git в data/eval.
SFR5C_OOD19 := data/eval/ood_queries_19.jsonl

# --examples 10000 вместо 10: файл читает Борис целиком, а не как примеры.
catalog-sfr5c: unhide
	SFR_DB_URL=$(SFR5C_DB_URL) uv run sfr etl backfill-mega
	SFR_DB_URL=$(SFR5C_DB_URL) uv run sfr etl dedup --apply \
		--decisions $(SFR5C_DEDUP_DECISIONS) --review-out $(SFR5C_DEDUP_REVIEW) --examples 10000
	SFR_DB_URL=$(SFR5C_DB_URL) uv run sfr etl build-profiles
	$(MAKE) export-sfr5c

export-sfr5c: unhide
	SFR_DB_URL=$(SFR5C_DB_URL) uv run sfr export jsonl --out $(SFR5C_PROFILES)
	SFR_DB_URL=$(SFR5C_DB_URL) uv run sfr export cards --out $(SFR5C_CARDS)

# Со штампом порогов из ApiSettings: с выкладки 26.09 это боевой индекс, и без
# штампа пересборка молча разоружала бы сверку (`thresholds_match: null`).
# Пока индекс был экспериментальным, штамп стоял бы ложный — тогда пороги
# ставились руками после калибровки (`sfr-match stamp-thresholds --index-dir …
# --none … --weak … --high …`); так же надо делать и при перекалибровке, до
# того как новые числа попадут в ApiSettings.
# Запускать только вне харнесса (docs/DECISIONS.md 18.09):
#   nohup sh -c 'make index-sfr5c && touch data/eval/index_sfr5c.done' \
#       > data/eval/index_sfr5c.log 2>&1 & disown
index-sfr5c: unhide
	uv run sfr-match index -m frida --clean --compose full \
		--profiles $(SFR5C_PROFILES) --index-root $(SFR5C_INDEX_ROOT)
	SFR_API_INDEX_ROOT=$(SFR5C_INDEX_ROOT) uv run python scripts/stamp_thresholds.py
	$(MAKE) stamp-data-date-sfr5c

# Дата данных каталога в meta.json (#16): самая свежая updated_date записи
# OpenAlex среди авторов каталога — её показывает плашка «обновлено» на профиле.
# БД только читается; пересборка индекса без новых данных даёт ту же дату.
stamp-data-date-sfr5c: unhide
	uv run python scripts/stamp_data_date.py --db-url $(SFR5C_DB_URL) \
		--index-dir $(SFR5C_INDEX_ROOT)/frida_clean

eval-sfr5c: unhide
	uv run sfr-match eval --models frida --clean --compose full \
		--index-root $(SFR5C_INDEX_ROOT) --runs-dir $(SFR5C_RUNS)
	uv run sfr-match eval --models frida --clean --compose full --queries ood \
		--index-root $(SFR5C_INDEX_ROOT) --runs-dir $(SFR5C_OOD_RUNS)
	uv run sfr-match eval --models frida --clean --compose full --queries external \
		--index-root $(SFR5C_INDEX_ROOT) --runs-dir $(SFR5C_EXT_RUNS)
	uv run sfr-match pool --runs-dir $(SFR5C_RUNS) --index-root $(SFR5C_INDEX_ROOT) \
		--out data/eval/pool_sfr5c.jsonl
	uv run sfr-match pool --runs-dir $(SFR5C_OOD_RUNS) --queries ood \
		--index-root $(SFR5C_INDEX_ROOT) --out data/eval/pool_ood_sfr5c.jsonl
	uv run sfr-match pool --runs-dir $(SFR5C_EXT_RUNS) --queries external \
		--index-root $(SFR5C_INDEX_ROOT) --out data/eval/pool_external_sfr5c.jsonl

$(SFR5C_OOD19):
	git show a931af0^:packages/sfr-match/eval/ood_queries.jsonl > $@

# Таблица трёх точек 5 538 / потолок / 12 119 (§6.5 спеки). Склейки точки
# 12 119 пересчитываются заново из sfr5b.db — не берутся из старого JSON,
# чтобы поправка #94 попала в обе правые колонки.
# Цель **воспроизводит §4 и §6 по архиву измерения** (как `review-sfr5c` — §7):
# её выходы — трекаемые файлы отчёта, и на каталоге 9 002 с 17 посторонними она
# переписала бы их чужими числами (ревью выкладки, #126). Проверено 27.09 — оба
# JSON совпадают байт в байт. Калибровка выложенного индекса — `ood19-sfr5c`
# (19 посторонних) и `eval-sfr5c` + `analyze_sfr5.py` (17). Последняя команда —
# третий прогон тех же 135 решающих пар (#115): разброс судьи v2 ↔ v3, разбор
# по классам — §6 отчёта.
metrics-sfr5c: unhide $(SFR5C_OOD19)
	uv run python scripts/analyze_sfr5.py --runs-dir $(SFR5C_9010_RUNS) \
		--ood-runs-dir $(SFR5C_9010_OOD_RUNS) --ood-queries $(SFR5C_OOD19) \
		--profiles $(SFR5C_9010_PROFILES) --out docs/metrics/sfr5c_metrics.json
	uv run python scripts/sfr5c_three_points.py --cap-suffix sfr5c_9010 \
		--cap-db $(SFR5C_9010_DB) --ood-queries $(SFR5C_OOD19)
	uv run python scripts/sfr5c_rejudge_classes.py
	uv run python scripts/sfr5c_rejudge_classes.py \
		--v1 $(SFR5C_EVAL)/judgments_rejudge_sfr5c_v2.jsonl \
		--v2 $(SFR5C_EVAL)/judgments_rejudge_sfr5c_v3.jsonl \
		--v1-label "пересуд v2 (дневная рубрика)" --v2-label "пересуд v3 (с уточнениями)" \
		--out docs/metrics/sfr5c_rejudge_v2_v3.json

# Калибровка выложенного индекса 9 002 по тем 19 посторонним, на которых она
# считалась 26.09 (§13.4, колонка «(19)»; «18 из 19» в комментарии ApiSettings):
# прогон посторонних по 19 был перезаписан прогоном по 17 (#126). Выход — в
# data/eval, трекаемые файлы не трогаются.
ood19-sfr5c: unhide $(SFR5C_OOD19)
	uv run sfr-match eval --models frida --clean --compose full \
		--queries-file $(SFR5C_OOD19) \
		--index-root $(SFR5C_INDEX_ROOT) --runs-dir data/eval/runs_ood_sfr5c_19
	uv run python scripts/analyze_sfr5.py --runs-dir $(SFR5C_RUNS) \
		--ood-runs-dir data/eval/runs_ood_sfr5c_19 --ood-queries $(SFR5C_OOD19) \
		--profiles $(SFR5C_PROFILES) --out data/eval/metrics_sfr5c_ood19.json

# Качество выкладываемого индекса по двум разметкам (§13): слепой пересуд
# топ-5 — цифры для паспорта (#95), накопленная разметка — рядом для сравнения.
metrics-deploy-sfr5c: unhide
	uv run python scripts/sfr5c_deploy_metrics.py --runs $(SFR5C_RUNS)/frida_clean.json \
		--index-root $(SFR5C_INDEX_ROOT) \
		--judgments $(SFR5C_EVAL)/judgments_deploy_sfr5c.jsonl \
		--borderline $(SFR5C_EVAL)/judgments_borderline_deploy.md \
		--interval-out docs/metrics/sfr5c_deploy_interval.json \
		--out docs/metrics/sfr5c_deploy_metrics.json

# Слепой пул топ-5 golden set (24 in-domain + 6 edge = 150 пар) на пересуд
# субагентом `sfr-judge`: без поля judged, в порядке author_id. Оценки — в
# packages/sfr-match/eval/judgments_deploy_sfr5c.jsonl, накопленный
# judgments.jsonl не трогается (docs/DECISIONS.md 26.09, канонический судья).
pool-deploy-sfr5c: unhide
	uv run sfr-match pool --runs-dir $(SFR5C_RUNS) --index-root $(SFR5C_INDEX_ROOT) \
		--depth 5 --blind --out data/eval/pool_deploy_sfr5c.jsonl

# Двадцать пар слепого пересуда на проверку человеку — отдельным файлом, чтобы
# не затереть выборку §7 (её читал Борис по #112). Пишет в data/eval/review и
# сверяет со снимком §13.5 в eval/ (#143).
review-deploy-sfr5c: unhide
	uv run sfr-match review-sample --n 20 --runs-dir $(SFR5C_RUNS) \
		--index-root $(SFR5C_INDEX_ROOT) \
		--judgments $(SFR5C_EVAL)/judgments_deploy_sfr5c.jsonl \
		--out $(SFR5C_REVIEW_DEPLOY)
	$(call compare_snapshot,$(SFR5C_EVAL)/judgments_for_review_deploy.md,$(SFR5C_REVIEW_DEPLOY),$(SFR5C_REVIEW_DIR)/judgments_for_review_deploy.diff)

# #122: тот же слепой пересуд топ-5 — на прежнем боевом индексе 5 538
# (data/indexes_sfr5 и прогон runs_sfr5 замороженного блока SFR-5; на VPS
# этого индекса уже нет). Пара «5 538 → 9 002» одним судьёй и одной рубрикой —
# §13.11 отчёта. Те же CLI и скрипт, что у выкладки, другие входы; накопленный
# judgments.jsonl не трогается. Вторая команда метрик — совпадение двух слепых
# прогонов на общих парах двух пятёрок (не #115: пул другой).
pool-base-blind-sfr5c: unhide
	uv run sfr-match pool --runs-dir $(SFR5_RUNS) --index-root $(SFR5_INDEX_ROOT) \
		--depth 5 --blind --out data/eval/pool_base5538_blind.jsonl

metrics-base-blind-sfr5c: unhide
	uv run python scripts/sfr5c_deploy_metrics.py --runs $(SFR5_RUNS)/frida_clean.json \
		--index-root $(SFR5_INDEX_ROOT) \
		--judgments $(SFR5C_EVAL)/judgments_base5538_blind.jsonl \
		--borderline $(SFR5C_EVAL)/judgments_borderline_base5538.md \
		--interval-out docs/metrics/sfr5c_base_blind_interval.json \
		--out docs/metrics/sfr5c_base_blind_metrics.json
	uv run python scripts/sfr5c_rejudge_classes.py \
		--v1 $(SFR5C_EVAL)/judgments_deploy_sfr5c.jsonl \
		--v2 $(SFR5C_EVAL)/judgments_base5538_blind.jsonl \
		--v1-label "слепой пересуд 9 002" --v2-label "слепой пересуд 5 538" \
		--out docs/metrics/sfr5c_blind_overlap_classes.json

# Выборка для человека (§7 отчёта) целиком одной командой: раньше два раздела
# склеивались руками и повторный прогон файл не воспроизводил (#114). Колонки
# оценок — «было → v1 → v2»: оба пересуда рядом, расхождения помечены ⚠.
# Цель **воспроизводит §7 по архиву измерения** (точка «потолок 9 010»,
# `*_sfr5c_9010`), а не считает текущий каталог: её выход сверяется с
# трекаемым файлом, который Борис читал по #112, и на каталоге 9 002 он получил
# бы чужие данные (ревью выкладки SFR-5c). Пул решающих пар из архива совпадает
# с тем, что входил в пересуды v1/v2, — пересчёт байт в байт. Выборка по
# выложенному каталогу — `review-deploy-sfr5c`. С #143 выход — в
# data/eval/review, трекаемый файл §7 в eval/ — снимок, цель его не пишет.
review-sfr5c: unhide
	uv run sfr-match review-sample --n 20 --runs-dir $(SFR5C_9010_RUNS) \
		--index-root $(SFR5C_9010_INDEX_ROOT) --iteration SFR-5c --out $(SFR5C_SAMPLE)
	uv run python scripts/sfr5c_decisive_pairs.py \
		--cap-runs $(SFR5C_9010_RUNS) --cap-profiles $(SFR5C_9010_PROFILES) \
		--pool-out data/eval/pool_rejudge_sfr5c.jsonl \
		--rejudged v1=$(SFR5C_EVAL)/judgments_rejudge_sfr5c.jsonl \
		--rejudged v2=$(SFR5C_EVAL)/judgments_rejudge_sfr5c_v2.jsonl \
		--section-out $(SFR5C_DECISIVE) --sample $(SFR5C_SAMPLE) --out $(SFR5C_REVIEW)
	$(call compare_snapshot,$(SFR5C_EVAL)/judgments_for_review_sfr5c.md,$(SFR5C_REVIEW),$(SFR5C_REVIEW_DIR)/judgments_for_review_sfr5c.diff)

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
SFR_COMPOSE_PROJECT ?= sfr-local
SFR_LOCAL_PORT ?= 8080
SFR_COMPOSE_SUBNET ?= 172.29.162.0/24
SFR_COMPOSE_WEB_IP ?= 172.29.162.3
SFR_COMPOSE_IP_RANGE ?= $(subst .0/24,.128/25,$(SFR_COMPOSE_SUBNET))
DEPLOY_COMPOSE := docker compose -p $(SFR_COMPOSE_PROJECT) -f deploy/docker-compose.yml -f deploy/docker-compose.local.yml
DEPLOY_ENV = SFR_COMPOSE_PROJECT=$(SFR_COMPOSE_PROJECT) SFR_LOCAL_PORT=$(SFR_LOCAL_PORT) \
	SFR_COMPOSE_SUBNET=$(SFR_COMPOSE_SUBNET) SFR_COMPOSE_WEB_IP=$(SFR_COMPOSE_WEB_IP) \
	SFR_COMPOSE_IP_RANGE=$(SFR_COMPOSE_IP_RANGE) \
	SFR_HF_CACHE=$$HOME/.cache/huggingface SITE_ADDRESS=http://localhost:8080 \
	NEXT_PUBLIC_SITE_URL=http://localhost:$(SFR_LOCAL_PORT) REVALIDATE_SECRET=local-rehearsal \
	SFR_ANALYTICS_MIGRATION_PASSWORD=$${SFR_ANALYTICS_MIGRATION_PASSWORD:-local-rehearsal-migration} \
	SFR_ANALYTICS_RUNTIME_PASSWORD=$${SFR_ANALYTICS_RUNTIME_PASSWORD:-local-rehearsal-runtime} \
	SFR_ANALYTICS_READER_PASSWORD=$${SFR_ANALYTICS_READER_PASSWORD:-local-rehearsal-reader} \
	SFR_ANALYTICS_RELEASE=$(shell git rev-parse HEAD)

deploy-local:
	$(DEPLOY_ENV) $(DEPLOY_COMPOSE) up -d --build --wait --wait-timeout 300
	$(DEPLOY_ENV) $(DEPLOY_COMPOSE) run --rm analytics-migrate
	@for n in $$(seq 1 240); do curl -sf -o /dev/null http://localhost:$(SFR_LOCAL_PORT)/ && break; sleep 1; done
	@curl -sf -o /dev/null http://localhost:$(SFR_LOCAL_PORT)/
	@curl -sf -X POST -H "x-revalidate-secret: local-rehearsal" \
		http://localhost:$(SFR_LOCAL_PORT)/api/revalidate
	@echo "прокси: http://localhost:$(SFR_LOCAL_PORT) · проект: $(SFR_COMPOSE_PROJECT)"

deploy-local-down:
	$(DEPLOY_ENV) $(DEPLOY_COMPOSE) down

# Operator-only private analytics. Credentials from environment, never arguments.
.PHONY: analytics-report analytics-check analytics-export analytics-replay analytics-migrate \
	analytics-backup analytics-restore-check analytics-pull analytics-test-postgres
analytics-report: unhide
	uv run python scripts/analytics.py report $(ANALYTICS_ARGS)

analytics-check: unhide
	uv run python scripts/analytics.py check $(ANALYTICS_ARGS)

analytics-export: unhide
	uv run python scripts/analytics.py export $(ANALYTICS_ARGS)

analytics-replay: unhide
	uv run python scripts/analytics.py replay $(ANALYTICS_ARGS)

analytics-migrate: unhide
	uv run python -m sfr_api.analytics.migrate --runtime-role sfr_runtime --reader-role sfr_reader

analytics-backup: unhide
	uv run python scripts/analytics_backup.py backup $(ANALYTICS_ARGS)

analytics-restore-check: unhide
	uv run python scripts/analytics_backup.py verify $(ANALYTICS_ARGS)

analytics-pull: unhide
	uv run python scripts/analytics_pull.py $(ANALYTICS_ARGS)

analytics-test-postgres: unhide
	uv run pytest apps/api/tests/test_analytics_pg.py --no-cov

# ---------------------------------------------------------------------------
# SFR-4b: аудит безопасности (статический анализ + зависимости + секреты).
# Полный список инструментов и политика падения — docs/reports/SFR4b_REPORT.md.
# Питоновские сканеры — из uv-группы security, бинарные (gitleaks, trivy,
# hadolint) — из PATH или из запиненного docker-образа; чего нет — SKIP.
# ---------------------------------------------------------------------------
audit: unhide
	uv run --group security python scripts/audit.py $(AUDIT_ARGS)

# ---------------------------------------------------------------------------
# Доска «SFR — задачи»: поля Status / Priority / Iteration — производные от
# лейблов issues. Правила маппинга — в докстринге scripts/gh_board_sync.py и
# в AGENTS.md. Идемпотентно: повторный прогон ничего не меняет.
# Нужен scope project у gh (gh auth refresh -s project).
# ---------------------------------------------------------------------------
board-sync: unhide
	uv run python scripts/gh_board_sync.py

board-sync-dry: unhide
	uv run python scripts/gh_board_sync.py --dry-run

# Гигиена issues: лейблы, приоритеты, залежавшееся, кандидаты в дубли.
# Ничего не чинит — печатает отчёт; правила таксономии — AGENTS.md.
issues-audit: unhide
	uv run python scripts/gh_issues_audit.py $(AUDIT_ISSUES_ARGS)

# Хук-граница на push/merge (#129): что отклоняется и что проходит — на python3
# из PATH, на системном /usr/bin/python3 и без python3. В CI не гоняется.
hooks-test:
	bash .claude/hooks/test_block_push.sh
	python3 -m unittest discover -s scripts -p 'test_check*.py'

# Согласованность живых документов (#144): пути и старые адреса в md, блок «Состояние»
# DECISIONS против брифа, meta.json боевого индекса и ApiSettings, открытая итерация,
# версия спеки MVP. Только stdlib, идёт в CI. `-live` — плюс сверка с боевым /api/health.
docs-check:
	python3 scripts/docs_check.py

docs-check-live:
	python3 scripts/docs_check.py --live

# Только чтение PR: текущее подтверждение ревью и checks/web/audit.
# Номер обязателен; это готовность к передаче, не разрешение на merge.
.PHONY: handoff-check
handoff-check: export SFR_HANDOFF_PR=$(PR)
handoff-check:
	python3 scripts/check_handoff.py --pr "$$SFR_HANDOFF_PR"

.PHONY: analytics-rotate
analytics-rotate: unhide
	uv run python scripts/analytics_rotate.py

.PHONY: analytics-test-caddy
analytics-test-caddy: unhide
	uv run python scripts/check_caddy_logging.py $(CADDY_TEST_ARGS)
