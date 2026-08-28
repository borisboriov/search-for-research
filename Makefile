.PHONY: setup lint typecheck test test-integration etl report format

setup:
	uv sync --all-packages
	uv run pre-commit install

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy packages/sfr-core/src/sfr_core packages/sfr-etl/src/sfr_etl

test:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest -m integration --no-cov

# Full ETL pipeline. Requires an institution resolved beforehand:
#   uv run sfr institutions resolve "Moscow Institute of Physics and Technology"
etl:
	uv run sfr etl authors --max 300
	uv run sfr etl works --since-years 5 --per-author 25
	uv run sfr etl build-profiles
	uv run sfr export jsonl --out data/exports/profiles.jsonl

report:
	uv run sfr report
