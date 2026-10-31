"""Согласованность живых документов: `make docs-check` (#144, мера A1 диеты документов).

Ловит рассинхрон до того, как его прочитает следующий тред или сессия:

1. Пути в обратных кавычках и локальные Markdown-ссылки/якоря существуют.
2. В живых документах нет старых адресов (`docs/SFR<N>_REPORT.md` без `reports/`,
   `docs/product/edits/`, копии в проекте Claude, `SFR_TODO.md`, `GITHUB_WORKFLOW.md`).
3. Бриф «Где мы сейчас» — единственное принятое состояние; его факты обязательны.
4. Бриф совпадает с `meta.json` боевого индекса (локально,
   `data/indexes_sfr5c/frida_clean/meta.json` или `SFR_INDEX_META`) и с порогами
   в `ApiSettings` (`apps/api/src/sfr_api/settings.py`).
5. «Открытой итерации нет» ↔ в корне нет `SPEC_*.md`; если открыта — спека названа и лежит в корне.
6. Версия спеки MVP в её шапке совпадает с версией, названной в брифе.
7. Success@k сверяется с указанным в брифе JSON слепого измерения.
8. `--live`: `/api/health` боевого сервиса — profiles_count, institutions_count,
   index_version, пороги — против брифа.

Только стандартная библиотека. Расхождения печатаются списком, код возврата 1.
Исторические упоминания путей не проверяются; действующие Markdown-ссылки
проверяются и в историческом тексте. Внешние и частные пути вне репозитория
не открываются. Проверка структуры ссылок не устанавливает истинность текста.

    python3 scripts/docs_check.py          # локально и в CI
    python3 scripts/docs_check.py --live   # плюс сверка с боевым /health
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]

LIVE_DOCS = [
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "enrichment/README.md",
    "enrichment/research/INDEX.md",
    "docs/README.md",
    "docs/product/README.md",
    "docs/product/brief.md",
    "docs/DECISIONS.md",
    "docs/product/mvp_spec.md",
    "docs/product/nir_vkrs.md",
    "docs/product/course_grading_NIR3.md",
    "docs/product/course_grading_VKRS.md",
    "docs/product/research/profile_evidence_review_2026-10.md",
    "docs/product/grants_tracker_2026-2027.md",
    "docs/product/market_stretch_map_2026-08-08.md",
    "docs/PILOT_TEST_GUIDE.md",
    "deploy/README.md",
    "packages/sfr-match/eval/README.md",
    "apps/api/README.md",
    "apps/web/README.md",
    ".claude/agents/sfr-reviewer.md",
    ".claude/agents/sfr-judge.md",
    ".claude/commands/issues.md",
    ".claude/commands/review-iteration.md",
    ".agents/skills/issues/SKILL.md",
    ".agents/skills/review-iteration/SKILL.md",
    ".agents/skills/sfr-session-prompt/SKILL.md",
    ".agents/skills/sfr-verify-session/SKILL.md",
    ".agents/skills/sfr-close-round/SKILL.md",
]

# Строка — история, старые адреса в ней стоят намеренно.
HISTORY = re.compile(
    r"удал[её]н|снят[оы]?\b|до \d\d\.\d\d|git show|старые пути|истори|раньше|переехал|"
    r"перенес|прежн|"
    r"больше не|не ведётся|заморожен|отменён|влит",
    re.IGNORECASE,
)
# Строка — пример имени (шаблон, будущая итерация), а не ссылка на файл.
EXAMPLE = re.compile(r"Именование|например|пример|шаблон|вида `", re.IGNORECASE)
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "data",
    ".next",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".idea",
}
# Файлы, которые живут только в gitignored `data/` — по имени не проверяем.
GENERATED = {"meta.json"}
ITERATION = re.compile(r"SFR(\d+[a-z]?)")
PATH_TOKEN = re.compile(r"`([^`\n]+)`")
REPO_DIRS = (
    "docs/",
    "enrichment/",
    "scripts/",
    "packages/",
    "apps/",
    "deploy/",
    "security/",
    ".claude/",
    ".agents/",
    ".codex/",
    ".github/",
)
ROOT_FILES = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*\.(md|py|sh|json|yml|yaml|toml|txt|example)$")

STALE = [
    (
        re.compile(r"(?<![\w/])docs/SFR\d+[a-z]?_REPORT\.md"),
        "старый путь отчёта — теперь docs/reports/",
    ),
    (
        re.compile(r"(?<![\w/])docs/sfr\d+[a-z]?_[a-z_]+\.json"),
        "старый путь JSON — теперь docs/metrics/",
    ),
    (
        re.compile(r"docs/product/edits/"),
        "файлов-предложений больше нет (27.09.2026) — issue `human` `docs`",
    ),
    (
        re.compile(r"claude/Search_for_research_project_brief|MVP_спека_и_план"),
        "копий в проекте Claude нет с 27.09.2026",
    ),
    (
        re.compile(r"SFR_TODO\.md|TODO_BORIS\.md"),
        "TODO-файлы не ведутся с 12.09.2026 — GitHub Issues",
    ),
    (re.compile(r"GITHUB_WORKFLOW\.md"), "файл удалён 13.09.2026 — правила в CLAUDE.md"),
    (re.compile(r"SJM НИР"), "план курса — docs/product/course_plan_NIR3-4.pdf"),
]

NUM = r"(\d{1,3}(?: \d{3})*)"
PCT = r"(\d{1,3},\d)"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def to_int(text: str) -> int:
    return int(text.replace(" ", "").replace(" ", ""))


def is_ignored(rel: str) -> bool:
    """Путь из .gitignore — локальный файл (`settings.local.json`): в CI его нет, это не ошибка."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", rel],
            cwd=ROOT,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def repo_basenames() -> set[str]:
    """Имена файлов репозитория — для путей, названных без каталога (`meta.json`, `brief.md`)."""
    names: set[str] = set()
    for _dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        names.update(filenames)
    return names


def known_iterations() -> set[str]:
    """Коды итераций со спекой или отчётом: `SPEC_SFR7_*.md` без них — будущее имя, не ссылка."""
    codes: set[str] = set()
    for path in (
        list(ROOT.glob("SPEC_*.md"))
        + list((ROOT / "docs/specs").glob("*.md"))
        + list((ROOT / "docs/reports").glob("*.md"))
    ):
        codes.update(m.group(1) for m in ITERATION.finditer(path.name))
    return codes


def live_docs() -> list[str]:
    """Тематические документы подхватываются, когда появляются в проверяемой ветке."""
    return list(
        dict.fromkeys(
            LIVE_DOCS
            + sorted(
                str(path.relative_to(ROOT))
                for path in (ROOT / "docs/product/monetization").rglob("*.md")
            )
        )
    )


def prose_lines(text: str) -> Iterator[tuple[int, str]]:
    """Не считать fenced code и HTML-комментарии действующими ссылками/заголовками."""
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group().count("\n"), text, flags=re.S)
    fence = ""
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            run = marker.group(1)
            if not fence:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = ""
            continue
        if not fence:
            yield number, line


def markdown_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    headings: set[str] = set()
    previous = ""
    for _, line in prose_lines(text):
        no_code = re.sub(r"(`+).*?\1", "", line)
        anchors.update(re.findall(r"\b(?:id|name)=[\"']([^\"']+)[\"']", no_code))
        heading = re.match(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+\s*)?$", line)
        title = heading.group(1) if heading else ""
        if previous and re.fullmatch(r" {0,3}(?:=+|-+)\s*", line):
            title = previous
        previous = line.strip()
        if not title:
            continue
        title = re.sub(r"!?\[([^]]*)\]\([^)]*\)", r"\1", title)
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).lower()
        slug = re.sub(r"[^\w\- ]", "", title).replace(" ", "-")
        unique, suffix = slug, 0
        while unique in headings:
            suffix += 1
            unique = f"{slug}-{suffix}"
        headings.add(unique)
        anchors.add(unique)
    return anchors


def markdown_links(text: str) -> Iterator[tuple[int, str]]:
    # Destinations support angle brackets, escapes and balanced parentheses.
    # Reference definitions are checked once, at the definition's location.
    for number, line in prose_lines(text):
        line = re.sub(r"(`+).*?\1", "", line)
        reference = re.match(r"^ {0,3}\[[^]]+\]:\s*", line)
        starts = [reference.end()] if reference else []
        starts += [match.end() for match in re.finditer(r"!?\[[^]\n]*\]\(\s*", line)]
        for start in starts:
            if start >= len(line):
                continue
            if line[start] == "<":
                end = line.find(">", start + 1)
                if end >= 0:
                    yield number, line[start + 1 : end]
                continue
            end, depth = start, 0
            while end < len(line):
                char = line[end]
                if char == "\\" and end + 1 < len(line):
                    end += 2
                    continue
                if char.isspace() or (char == ")" and depth == 0):
                    break
                depth += (char == "(") - (char == ")")
                end += 1
            yield number, line[start:end]


def check_markdown_links(rel: str, text: str, findings: list[str]) -> None:
    for number, href in markdown_links(text):
        href = html.unescape(re.sub(r"\\([() ])", r"\1", href))
        link = urlsplit(href)
        if link.scheme or link.netloc or link.path.startswith(("/", "~")):
            continue
        target = ((ROOT / rel).parent / unquote(link.path)).resolve() if link.path else ROOT / rel
        if not target.is_relative_to(ROOT.resolve()):
            continue  # Private local sources are outside this repository check.
        if not target.exists():
            if not is_ignored(str(target.relative_to(ROOT))):
                findings.append(f"{rel}:{number}: ссылка `{href}` — файл не существует")
        elif link.fragment and target.suffix.lower() == ".md":
            anchors = markdown_anchors(target.read_text(encoding="utf-8"))
            if unquote(link.fragment) not in anchors:
                findings.append(f"{rel}:{number}: ссылка `{href}` — якорь не существует")


def check_paths(findings: list[str]) -> None:
    basenames = repo_basenames()
    iterations = known_iterations()
    for rel in live_docs():
        path = ROOT / rel
        if not path.exists():
            findings.append(f"{rel}: файла нет, а он в списке живых документов скрипта")
            continue
        text = path.read_text(encoding="utf-8")
        if rel == "docs/DECISIONS.md":
            text = text.split("\n## 2026-", 1)[0]
        check_markdown_links(rel, text, findings)
        for lineno, line in enumerate(text.split("\n"), 1):
            if HISTORY.search(line) or EXAMPLE.search(line):
                continue
            for token in PATH_TOKEN.findall(line):
                token = token.strip()
                if any(ch in token for ch in "<>*…{}$ ") or token.startswith(("~", "/", "http")):
                    continue
                if (
                    token.startswith("data/")
                    or ".env" in token
                    or os.path.basename(token) in GENERATED
                ):
                    continue
                codes = {m.group(1) for m in ITERATION.finditer(token)}
                if codes and not codes & iterations:
                    continue  # имя будущей итерации
                if token.startswith(REPO_DIRS):
                    target = token.split("#", 1)[0].rstrip("/")
                    if not (ROOT / target).exists() and not is_ignored(target):
                        findings.append(f"{rel}:{lineno}: путь `{token}` не существует")
                elif ROOT_FILES.match(token) and token not in basenames:
                    findings.append(f"{rel}:{lineno}: файла `{token}` нет нигде в репозитории")
            for pattern, why in STALE:
                if pattern.search(line):
                    findings.append(f"{rel}:{lineno}: {why}: {line.strip()[:100]}")


def brief_screen() -> str:
    text = read("docs/product/brief.md")
    m = re.search(r"^## Где мы сейчас.*?(?=^## )", text, re.M | re.S)
    if not m:
        raise SystemExit("docs/product/brief.md: не найден раздел «## Где мы сейчас»")
    return m.group(0)


def facts(text: str, where: str, findings: list[str]) -> dict[str, object]:
    out: dict[str, object] = {}
    m = re.search(NUM + r"\s+профил", text)
    if m:
        out["profiles"] = to_int(m.group(1))
    m = re.search(r"(\d+)\s+вуз", text)
    if m:
        out["institutions"] = int(m.group(1))
    m = re.search(r"(0\.\d\d)\s*/\s*(0\.\d\d)\s*/\s*(0\.\d\d)", text)
    if m:
        out["thresholds"] = tuple(float(x) for x in m.groups())
    m = re.search(r"(frida_clean-\d+p-[0-9a-f]{8})", text)
    if m:
        out["index_version"] = m.group(1)
    m = re.search(r"Success@5\s*=?\s*" + PCT + r"\s*%", text)
    if m:
        out["s5"] = m.group(1)
    m = re.search(r"Success@1\s*=?\s*" + PCT + r"\s*%", text)
    if m:
        out["s1"] = m.group(1)
    for key in ("profiles", "institutions", "index_version", "thresholds", "s5", "s1"):
        if key not in out:
            findings.append(
                f"{where}: не удалось прочитать «{key}» — формулировку изменили? "
                "(скрипт ждёт «N профилей», «0.xx / 0.xx / 0.xx», «Success@5 = N,N %»)"
            )
    return out


def compare(a: dict[str, object], b: dict[str, object], where: str, findings: list[str]) -> None:
    for key in sorted(set(a) & set(b)):
        if a[key] != b[key]:
            findings.append(f"{where}: {key} — {a[key]} против {b[key]}")


def check_brief(findings: list[str]) -> dict[str, object]:
    return facts(brief_screen(), "бриф «Где мы сейчас»", findings)


def check_brief_metrics(state: dict[str, object], findings: list[str]) -> None:
    """Check the accepted quality claims against their linked evidence, not another summary."""
    links = re.findall(r"\]\((\.\./metrics/[A-Za-z0-9_.-]+\.json)\)", brief_screen())
    if len(links) != 1:
        findings.append("бриф: нужна одна ссылка на JSON канонического измерения качества")
        return
    path = (ROOT / "docs/product" / links[0]).resolve()
    try:
        metrics = json.loads(path.read_text(encoding="utf-8"))
        measured = metrics["sets"]["golden_in_domain_24"]["blind"]
        expected = {
            "profiles": metrics["n_profiles"],
            "index_version": metrics["index_version"],
            "s5": f"{measured['success_at_5'] * 100:.1f}".replace(".", ","),
            "s1": f"{measured['success_at_1'] * 100:.1f}".replace(".", ","),
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        findings.append(f"бриф: не удалось проверить измерение {links[0]} ({exc})")
        return
    compare(state, expected, "бриф «Где мы сейчас» ≠ измерение слепого судьи", findings)


def check_state_vs_index(state: dict[str, object], findings: list[str]) -> None:
    meta_path = Path(
        os.environ.get("SFR_INDEX_META", ROOT / "data/indexes_sfr5c/frida_clean/meta.json")
    )
    if not meta_path.exists():
        print(f"  (meta.json боевого индекса не найден: {meta_path} — сверка с индексом пропущена)")
    else:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        th = meta.get("thresholds") or {}
        local = {
            "profiles": meta.get("n_profiles"),
            "thresholds": (th.get("none"), th.get("weak"), th.get("high")),
            "index_version": "{}_{}-{}p-{}".format(
                meta.get("model_key"),
                "clean" if meta.get("clean") else "raw",
                meta.get("n_profiles"),
                str(meta.get("corpus_sha", ""))[:8],
            ),
        }
        shown = meta_path.relative_to(ROOT) if meta_path.is_relative_to(ROOT) else meta_path
        compare(
            state,
            local,
            f"бриф «Где мы сейчас» ≠ {shown}",
            findings,
        )
    settings = read("apps/api/src/sfr_api/settings.py")
    values = []
    for name in ("score_threshold", "score_weak", "score_high"):
        m = re.search(rf"^\s*{name}: float = (0\.\d+)", settings, re.M)
        values.append(float(m.group(1)) if m else None)
    if "thresholds" in state and tuple(values) != state["thresholds"]:
        findings.append(
            f"бриф «Где мы сейчас» ≠ ApiSettings: пороги {state['thresholds']} "
            f"против {tuple(values)}"
        )


def check_iteration(findings: list[str]) -> None:
    state = brief_screen()
    specs = sorted(p.name for p in ROOT.glob("SPEC_*.md"))
    says_none = "Открытой итерации нет" in state
    if says_none and specs:
        findings.append(
            f"бриф «Где мы сейчас»: «открытой итерации нет», но в корне лежит {', '.join(specs)}"
        )
    if not says_none:
        named = re.findall(r"SPEC_SFR[\w-]+\.md", state)
        if not named:
            findings.append(
                "бриф «Где мы сейчас»: открытая итерация не названа спекой `SPEC_SFR<N>*.md`"
            )
        for name in named:
            if name not in specs:
                findings.append(
                    f"бриф «Где мы сейчас»: спека {name} названа открытой, но в корне её нет"
                )


def check_spec_version(findings: list[str]) -> None:
    m_spec = re.search(r"^\*\*Версия:\*\* v(\d+\.\d+)", read("docs/product/mvp_spec.md"), re.M)
    m_brief = re.search(r"Спека MVP — v(\d+\.\d+)", brief_screen())
    if m_spec and m_brief and m_spec.group(1) != m_brief.group(1):
        findings.append(
            f"версия спеки MVP: шапка v{m_spec.group(1)}, бриф называет v{m_brief.group(1)}"
        )
    elif not (m_spec and m_brief):
        findings.append(
            "версия спеки MVP: не найдена в шапке спеки или в брифе («Спека MVP — vN.N»)"
        )


def check_live(state: dict[str, object], findings: list[str], url: str) -> None:
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            health = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        findings.append(f"{url}: не отвечает ({exc})")
        return
    live = {
        "profiles": health.get("profiles_count"),
        "institutions": health.get("institutions_count"),
        "index_version": health.get("index_version"),
        "thresholds": (
            health.get("score_threshold"),
            health.get("score_weak"),
            health.get("score_high"),
        ),
    }
    compare(state, live, "бриф «Где мы сейчас» ≠ боевой /api/health", findings)
    if health.get("thresholds_match") is False:
        findings.append(
            "боевой /api/health: thresholds_match = false — пороги индекса и сервиса разошлись"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--live", action="store_true", help="сверить бриф с боевым /api/health")
    parser.add_argument("--url", default="https://search-for-research.ru/api/health")
    args = parser.parse_args()
    findings: list[str] = []
    check_paths(findings)
    state = check_brief(findings)
    check_brief_metrics(state, findings)
    check_state_vs_index(state, findings)
    check_iteration(findings)
    check_spec_version(findings)
    if args.live:
        check_live(state, findings, args.url)
    if findings:
        print(f"docs-check: расхождений — {len(findings)}")
        for item in findings:
            print(f"  - {item}")
        return 1
    print(
        "docs-check: пути, якоря и проверяемые показатели согласованы"
        + (" (включая боевой /health)" if args.live else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
