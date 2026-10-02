"""Синхронизировать поля доски «SFR — задачи» с лейблами и состоянием issues.

Лейблы — источник истины, поля доски (Status / Priority / Iteration) — производные
от них. Руками поля не проставляются: после любого треда достаточно `make board-sync`.
Через MCP-коннектор GitHub поля проектов не пишутся, поэтому всё идёт через `gh`
(нужен scope `project`: `gh auth refresh -s project`).

## Правила маппинга

**Priority** ← лейбл `P0` / `P1` / `P2` (опция доски ищется по префиксу — полные
имена вида «P1 — эта итерация» меняются без предупреждения). Нет лейбла — поле
не трогать.

**Status** — первое подошедшее правило сверху вниз:

1. issue закрыт → `Done` (закрытие сильнее всего остального);
2. на доске уже стоит `In Progress` → не трогать: это Борис поставил руками;
3. лейбл `blocked` → `Waiting` (ждёт внешнего события или другой задачи);
4. лейбл `decision` → `Todo`, кроме исключений из `STATUS_OVERRIDES`
   (там #67 с дедлайном 15.09 12:00 → `In Progress`; issue закрыт 14.09,
   так что правило 1 его перехватывает — исключение осталось как механизм);
5. остальные открытые → `Todo`.

Из правила 5 следует, что открытый элемент в статусе `Backlog` переедет в `Todo`:
`Backlog` в правилах не описан. Скрипт считает такие переходы отдельно и печатает
их числом — если `Backlog` используется осознанно, правило надо будет дописать.

**Iteration** — только после явного решения открыть итерацию и задания её
префикса в `CURRENT_ITERATION_PREFIX`. Пока значение `None`, поле не менять.
При открытой итерации её получают только открытые issues с лейблом `agent`
и milestone из `ITERATION_MILESTONES`. Закрытым и остальным Iteration не ставить.

Поле, для которого правило говорит «не трогать», остаётся как есть: скрипт ничего
не сбрасывает и пишет только отличающиеся значения, поэтому повторный запуск —
пустой (проверка: после применения `--dry-run` печатает ноль изменений).

Issues репозитория, которых на доске нет, добавляются (`gh project item-add`)
и проходят тот же маппинг.

Использование:

    uv run python scripts/gh_board_sync.py --dry-run   # план, ничего не меняет
    uv run python scripts/gh_board_sync.py             # применить
"""

import argparse
import json
import subprocess
import sys
from typing import Any

OWNER = "borisboriov"
PROJECT_NUMBER = "5"
REPO = "borisboriov/search-for-research"

#: Задаётся после явного решения открыть итерацию; будущий план не разрешает старт.
CURRENT_ITERATION_PREFIX: str | None = None

#: Milestones, задачи которых относятся к текущей итерации.
ITERATION_MILESTONES = {"Пилот 5 тестеров", "Аттестация НИР 3"}

#: Точечные исключения из правил Status: номер issue → статус.
STATUS_OVERRIDES = {67: "In Progress"}

PRIORITY_LABELS = ("P0", "P1", "P2")


def gh(*args: str) -> str:
    """Вызвать `gh` и вернуть stdout; непустой код возврата — понятная ошибка."""
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} -> {result.returncode}\n{result.stderr.strip()}")
    return result.stdout


def gh_json(*args: str) -> Any:
    return json.loads(gh(*args))


def check_scope() -> None:
    """Без scope `project` скрипт упрётся в права уже на первом item-edit."""
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, check=False)
    out = result.stdout + result.stderr
    if result.returncode != 0:
        raise SystemExit(f"gh auth status -> {result.returncode}\n{out.strip()}")
    scopes = [line for line in out.splitlines() if "Token scopes:" in line]
    if scopes and "'project'" not in scopes[0]:
        raise SystemExit("нет scope 'project' — выполните: gh auth refresh -s project")


def option_by_prefix(field: dict[str, Any], prefix: str) -> dict[str, str] | None:
    """Найти опцию single-select по префиксу имени (полные имена меняются)."""
    for option in field.get("options", []):
        if option["name"].startswith(prefix):
            return dict(option)
    return None


def target_status(issue: dict[str, Any], current: str | None) -> str | None:
    labels = issue["label_names"]
    if issue["state"] == "CLOSED":
        return "Done"
    if (current or "").lower() == "in progress":
        return None
    if issue["number"] in STATUS_OVERRIDES:
        return STATUS_OVERRIDES[issue["number"]]
    if "blocked" in labels:
        return "Waiting"
    return "Todo"


def target_priority(issue: dict[str, Any]) -> str | None:
    for label in PRIORITY_LABELS:
        if label in issue["label_names"]:
            return label
    return None


def target_iteration(issue: dict[str, Any]) -> str | None:
    if CURRENT_ITERATION_PREFIX is None or issue["state"] != "OPEN":
        return None
    if "agent" not in issue["label_names"]:
        return None
    if issue["milestone"] not in ITERATION_MILESTONES:
        return None
    return CURRENT_ITERATION_PREFIX


def fetch_issues() -> dict[int, dict[str, Any]]:
    raw = gh_json(
        "issue",
        "list",
        "--repo",
        REPO,
        "--state",
        "all",
        "--limit",
        "500",
        "--json",
        "number,state,title,labels,milestone,url",
    )
    issues = {}
    for issue in raw:
        issue["label_names"] = {label["name"] for label in issue["labels"]}
        issue["milestone"] = (issue["milestone"] or {}).get("title")
        issues[issue["number"]] = issue
    return issues


def fetch_items() -> dict[int, dict[str, Any]]:
    raw = gh_json(
        "project",
        "item-list",
        PROJECT_NUMBER,
        "--owner",
        OWNER,
        "--limit",
        "500",
        "--format",
        "json",
    )
    items = {}
    for item in raw["items"]:
        content = item.get("content") or {}
        if content.get("type") != "Issue" or content.get("repository") != REPO:
            continue
        items[content["number"]] = item
    return items


def add_item(issue: dict[str, Any], dry_run: bool) -> dict[str, Any] | None:
    """Добавить issue на доску; вернуть новый элемент (в dry-run — None)."""
    if dry_run:
        return None
    created = gh_json(
        "project",
        "item-add",
        PROJECT_NUMBER,
        "--owner",
        OWNER,
        "--url",
        issue["url"],
        "--format",
        "json",
    )
    return {"id": created["id"], "status": None, "priority": None, "iteration": None}


def edit_field(project_id: str, item_id: str, field: dict[str, Any], option_id: str) -> None:
    gh(
        "project",
        "item-edit",
        "--project-id",
        project_id,
        "--id",
        item_id,
        "--field-id",
        field["id"],
        "--single-select-option-id",
        option_id,
    )


def plan_for(
    issue: dict[str, Any], item: dict[str, Any] | None
) -> dict[str, tuple[str | None, str]]:
    """Какие поля и на что менять: имя поля → (было, префикс нового значения)."""
    current = {
        "Status": (item or {}).get("status"),
        "Priority": (item or {}).get("priority"),
        "Iteration": (item or {}).get("iteration"),
    }
    wanted = {
        "Status": target_status(issue, current["Status"]),
        "Priority": target_priority(issue),
        "Iteration": target_iteration(issue),
    }
    changes = {}
    for name, value in wanted.items():
        if value is None:
            continue
        was = current[name]
        if was is not None and was.startswith(value):
            continue
        changes[name] = (was, value)
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="напечатать план, ничего не менять")
    args = parser.parse_args()

    check_scope()

    project = gh_json("project", "view", PROJECT_NUMBER, "--owner", OWNER, "--format", "json")
    project_id = project["id"]
    fields_raw = gh_json(
        "project", "field-list", PROJECT_NUMBER, "--owner", OWNER, "--format", "json"
    )
    fields = {field["name"]: field for field in fields_raw["fields"]}
    missing_fields = {"Status", "Priority", "Iteration"} - fields.keys()
    if missing_fields:
        raise SystemExit(f"на доске нет полей: {', '.join(sorted(missing_fields))}")

    issues = fetch_issues()
    items = fetch_items()

    added: list[int] = []
    planned = 0
    skipped: list[str] = []
    backlog_to_todo = 0

    for number in sorted(issues):
        issue = issues[number]
        item = items.get(number)
        if item is None:
            added.append(number)
            print(f"#{number:>3}  + на доску: {issue['title'][:60]}")
            item = add_item(issue, args.dry_run)

        changes = plan_for(issue, item)
        for name, (was, wanted) in changes.items():
            field = fields[name]
            option = option_by_prefix(field, wanted)
            if option is None:
                skipped.append(f"#{number} {name}: на доске нет опции «{wanted}»")
                continue
            if name == "Status" and (was or "").lower() == "backlog":
                backlog_to_todo += 1
            print(f"#{number:>3}  {name}: {was or '—'} → {option['name']}")
            planned += 1
            if not args.dry_run and item is not None:
                edit_field(project_id, item["id"], field, option["id"])

    mode = "план (--dry-run)" if args.dry_run else "применено"
    print(
        f"\n{mode}: issues {len(issues)}, добавлено на доску {len(added)}, правок полей {planned}"
    )
    if backlog_to_todo:
        print(f"из статуса Backlog переведено в Todo: {backlog_to_todo}")
    for line in skipped:
        print(f"пропущено: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
