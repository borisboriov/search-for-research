"""Проверить гигиену issues: лейблы, приоритеты, залежавшееся, возможные дубли.

Механическая половина работы с задачами. Правила таксономии — в `CLAUDE.md`,
раздел «Задачи — в GitHub Issues»: у каждого issue ровно один лейбл «кто»
(`agent` / `human` / `sveta` / `decision`), один-два лейбла «область» и ровно
один приоритет (`P0`–`P2`). Скрипт ничего не чинит и не пишет в GitHub — только
читает и печатает отчёт; правки делает человек или `/issues`.

Разделение с `gh_board_sync.py`: тот владеет полями доски (они производные от
лейблов), этот — самими лейблами. Пересечение ровно одно: issues, которых нет
на доске, здесь показываются как «внимание», а добавляет их `make board-sync`.

Проверки делятся на две группы.

**Ошибки** — нарушение правила из `CLAUDE.md`, чинить:

* нет лейбла «кто» или их больше одного;
* нет лейбла «область» или их больше двух;
* нет приоритета или их больше одного.

**Внимание** — не нарушение, но стоит посмотреть:

* открытый `agent` без milestone: `make board-sync` не проставит ему Iteration,
  потому что правило итерации завязано на веху;
* открытый `blocked`: напоминание пересмотреть, не отпало ли внешнее событие;
* нет движения дольше `--stale-days` (по умолчанию 30);
* похожие заголовки среди открытых — кандидаты в дубли (коэффициент Жаккара по
  словам заголовка ≥ `--dup-threshold`); это подсказка, а не приговор. Порог 0.5
  намеренно строгий: на 0.3 сеть шире, но ловит вещи вроде «Подать заявку в X» и
  «Подать заявку на Y», которые дублями не являются;
* issues репозитория, которых нет на доске.

Использование:

    uv run python scripts/gh_issues_audit.py
    uv run python scripts/gh_issues_audit.py --open-only --stale-days 45
    uv run python scripts/gh_issues_audit.py --strict   # код возврата 1, если есть ошибки
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any

OWNER = "borisboriov"
PROJECT_NUMBER = "5"
REPO = "borisboriov/search-for-research"

WHO_LABELS = {"agent", "human", "sveta", "decision"}
AREA_LABELS = {"code", "docs", "product", "grant", "design", "legal"}
PRIORITY_LABELS = {"P0", "P1", "P2"}

#: Слова, которые есть почти в каждом заголовке и мешают искать дубли.
STOPWORDS = {
    "в",
    "на",
    "и",
    "для",
    "по",
    "с",
    "к",
    "из",
    "о",
    "об",
    "не",
    "что",
    "как",
    "до",
    "от",
    "за",
    "про",
}

TOKEN_RE = re.compile(r"[\w\-]+", re.UNICODE)


def gh_json(*args: str) -> Any:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} -> {result.returncode}\n{result.stderr.strip()}")
    return json.loads(result.stdout)


def fetch_issues(open_only: bool) -> list[dict[str, Any]]:
    raw = gh_json(
        "issue",
        "list",
        "--repo",
        REPO,
        "--state",
        "open" if open_only else "all",
        "--limit",
        "500",
        "--json",
        "number,state,title,labels,milestone,updatedAt",
    )
    for issue in raw:
        issue["label_names"] = {label["name"] for label in issue["labels"]}
        issue["milestone"] = (issue["milestone"] or {}).get("title")
    return sorted(raw, key=lambda i: i["number"])


def board_numbers() -> set[int]:
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
    return {
        item["content"]["number"]
        for item in raw["items"]
        if (item.get("content") or {}).get("type") == "Issue"
        and (item.get("content") or {}).get("repository") == REPO
    }


def tokens(title: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(title) if len(t) > 2} - STOPWORDS


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def label_errors(issue: dict[str, Any]) -> list[str]:
    labels = issue["label_names"]
    problems = []
    who = labels & WHO_LABELS
    if not who:
        problems.append("нет лейбла «кто» (agent / human / sveta / decision)")
    elif len(who) > 1:
        problems.append(f"несколько лейблов «кто»: {', '.join(sorted(who))}")
    area = labels & AREA_LABELS
    if not area:
        problems.append("нет лейбла «область»")
    elif len(area) > 2:
        problems.append(f"больше двух областей: {', '.join(sorted(area))}")
    priority = labels & PRIORITY_LABELS
    if not priority:
        problems.append("нет приоритета P0/P1/P2")
    elif len(priority) > 1:
        problems.append(f"несколько приоритетов: {', '.join(sorted(priority))}")
    return problems


def stale_days(issue: dict[str, Any], now: datetime) -> int:
    updated = datetime.fromisoformat(issue["updatedAt"].replace("Z", "+00:00"))
    return (now - updated).days


def section(title: str, lines: list[str]) -> None:
    if not lines:
        return
    print(f"\n## {title} ({len(lines)})\n")
    for line in lines:
        print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--open-only", action="store_true", help="только открытые issues (по умолчанию все)"
    )
    parser.add_argument(
        "--stale-days", type=int, default=30, help="сколько дней без движения считать залежавшимся"
    )
    parser.add_argument(
        "--dup-threshold", type=float, default=0.5, help="порог схожести заголовков для дублей"
    )
    parser.add_argument(
        "--strict", action="store_true", help="код возврата 1, если есть ошибки таксономии"
    )
    args = parser.parse_args()

    issues = fetch_issues(args.open_only)
    on_board = board_numbers()
    now = datetime.now(UTC)
    opened = [i for i in issues if i["state"] == "OPEN"]

    errors: list[str] = []
    for issue in issues:
        for problem in label_errors(issue):
            state = "" if issue["state"] == "OPEN" else " [закрыт]"
            errors.append(f"#{issue['number']:>3}{state}  {problem} — {issue['title'][:58]}")

    agent_no_milestone = [
        f"#{i['number']:>3}  {i['title'][:70]}"
        for i in opened
        if "agent" in i["label_names"] and not i["milestone"]
    ]
    blocked = [
        f"#{i['number']:>3}  {i['title'][:70]}" for i in opened if "blocked" in i["label_names"]
    ]
    stale = [
        f"#{i['number']:>3}  {stale_days(i, now):>3} дн.  {i['title'][:62]}"
        for i in sorted(opened, key=lambda i: i["updatedAt"])
        if stale_days(i, now) >= args.stale_days
    ]
    missing = [f"#{n}" for n in sorted({i["number"] for i in issues} - on_board)]

    dups: list[str] = []
    for left_index, left in enumerate(opened):
        for right in opened[left_index + 1 :]:
            score = jaccard(tokens(left["title"]), tokens(right["title"]))
            if score >= args.dup_threshold:
                dups.append(
                    f"{score:.2f}  #{left['number']} {left['title'][:40]}"
                    f"  ↔  #{right['number']} {right['title'][:40]}"
                )

    print(f"# Гигиена issues: {len(issues)} шт. ({len(opened)} открытых), {REPO}")
    section("Ошибки таксономии — чинить", errors)
    section("Открытые `agent` без milestone — Iteration не проставится", agent_no_milestone)
    section("Открытые `blocked` — пересмотреть, не отпало ли препятствие", blocked)
    section(f"Без движения ≥ {args.stale_days} дн.", stale)
    section("Похожие заголовки — проверить на дубли", dups)
    if missing:
        section("Нет на доске — добавит `make board-sync`", [", ".join(missing)])

    print(
        f"\nитого: ошибок {len(errors)}, поводов посмотреть "
        f"{len(agent_no_milestone) + len(blocked) + len(stale) + len(dups) + len(missing)}"
    )
    return 1 if (errors and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
