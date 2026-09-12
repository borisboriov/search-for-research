# -*- coding: utf-8 -*-
"""Создаёт issues по migration/tasks.py. Идемпотентен: повторный запуск
пропускает уже созданные (сверка по заголовку через gh issue list).

Запуск:  python3 migration/create_issues.py [--limit N]
Результат: migration/bodies/<id>.md и migration/created.json (id → номер, url).
"""
import json, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import tasks  # noqa: E402

REPO = "borisboriov/search-for-research"
BODIES = HERE / "bodies"
STATE = HERE / "created.json"


def gh(*args, **kw):
    return subprocess.run(["gh", *args], check=True, capture_output=True,
                          text=True, **kw).stdout.strip()


def existing_titles():
    raw = gh("issue", "list", "--repo", REPO, "--state", "all",
             "--limit", "500", "--json", "number,title")
    return {i["title"]: i["number"] for i in json.loads(raw)}


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    BODIES.mkdir(exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    have = existing_titles()
    made = 0

    for t in tasks.T:
        body_path = BODIES / f"{t['id']}.md"
        body_path.write_text(t["body"] + "\n")

        if t["title"] in have:
            state[t["id"]] = {"number": have[t["title"]], "title": t["title"]}
            continue
        if limit is not None and made >= limit:
            continue

        labels = ",".join([t["who"], *t["area"], *t["extra"]])
        cmd = ["issue", "create", "--repo", REPO, "--title", t["title"],
               "--label", labels, "--body-file", str(body_path)]
        if t["milestone"]:
            cmd += ["--milestone", t["milestone"]]
        url = gh(*cmd)
        num = int(url.rstrip("/").rsplit("/", 1)[-1])
        state[t["id"]] = {"number": num, "title": t["title"], "url": url}
        made += 1
        print(f"{t['id']:>4}  #{num}  {t['title']}")
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        time.sleep(1.2)

    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    print(f"\nсоздано в этот заход: {made}; всего в состоянии: {len(state)}")


if __name__ == "__main__":
    main()
