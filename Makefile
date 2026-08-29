.PHONY: setup lint typecheck test test-integration test-slow etl report format unhide \
	index eval eval-report index-sfr2 eval-sfr2 api docker-build docker-up docker-down bench

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

# Full reproduction: build every index, run the golden set, regenerate the report.
eval: index
	uv run sfr-match eval --models $(shell echo $(MATCH_MODELS) | tr ' ' ',') --no-clean
	uv run sfr-match eval --models $(shell echo $(MATCH_MODELS) | tr ' ' ',') --clean
	uv run sfr-match pool
	uv run sfr-match report

# Report only (rankings and judgments already on disk).
eval-report: unhide
	uv run sfr-match report

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

api: unhide
	uv run uvicorn sfr_api.main:app --factory --host 127.0.0.1 --port 8000

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
