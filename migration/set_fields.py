# -*- coding: utf-8 -*-
"""Кладёт issues на доску «SFR — задачи» и выставляет Status / Iteration / Priority.

Запуск:  python3 migration/set_fields.py
Идемпотентен: item-add на уже добавленный issue возвращает существующий item.
Поля читаются из проекта по именам, id нигде не зашиты.
"""
import json, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import tasks  # noqa: E402

PROJECT = "5"
OWNER = "@me"
REPO_URL = "https://github.com/borisboriov/search-for-research/issues"
STATE = HERE / "created.json"

PRIO = {"P0": "P0 — блокирует", "P1": "P1 — эта итерация", "P2": "P2 — потом"}


def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def fields():
    raw = json.loads(gh("project", "field-list", PROJECT, "--owner", OWNER,
                        "--format", "json"))
    out = {}
    for f in raw["fields"]:
        if f.get("type") == "ProjectV2SingleSelectField":
            out[f["name"]] = (f["id"], {o["name"]: o["id"] for o in f["options"]})
    return out


def main():
    state = json.loads(STATE.read_text())
    proj = json.loads(gh("project", "view", PROJECT, "--owner", OWNER, "--format", "json"))
    pid = proj["id"]
    F = fields()

    for t in tasks.T:
        num = state[t["id"]]["number"]
        item = json.loads(gh("project", "item-add", PROJECT, "--owner", OWNER,
                             "--url", f"{REPO_URL}/{num}", "--format", "json"))["id"]
        for fname, value in (("Status", t["status"]),
                             ("Iteration", t["iteration"]),
                             ("Priority", PRIO[t["prio"]])):
            fid, opts = F[fname]
            gh("project", "item-edit", "--project-id", pid, "--id", item,
               "--field-id", fid, "--single-select-option-id", opts[value])
        state[t["id"]]["item"] = item
        print(f"{t['id']:>4}  #{num:<3} {t['status']:<11} {t['prio']}  {t['iteration']}")
        time.sleep(0.4)

    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    print(f"\nна доске: {len(tasks.T)}")


if __name__ == "__main__":
    main()
