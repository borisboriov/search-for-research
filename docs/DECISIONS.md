# DECISIONS — журнал решений (ADR-lite)

Формат: дата — решение — почему — альтернативы.

## 2026-08-28 — uv workspace с виртуальным корнем

Корневой `pyproject.toml` без build-system (сам по себе не пакет), два
workspace-пакета `sfr-core` и `sfr-etl` с hatchling. Dev-зависимости — в
dependency-group `dev` корня.
**Почему:** корень не содержит кода; hatchling — стабильный минимальный бэкенд.
**Альтернативы:** uv_build (моложе, меньше документации), setuptools (тяжелее).

## 2026-08-28 — конфиги инструментов в корневом pyproject.toml

ruff/mypy/pytest/coverage настроены один раз в корне, а не по-пакетно.
Разная строгость mypy — через per-module override (`sfr_core.*` strict).
**Почему:** один источник настроек, `make lint`/`typecheck`/`test` работают из корня.
**Альтернативы:** по-пакетные конфиги — дублирование и рассинхрон.

## 2026-08-28 — coverage: исключены CLI-обвязка и alembic

`omit = ["*/sfr_etl/cli.py", "*/alembic/*"]` — порог ≥80% считается по чистой
логике, как требует §5 SPEC («не считая CLI-обвязку и alembic»).
