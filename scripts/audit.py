"""Аудит безопасности одной командой (`make audit`, SFR-4b).

Семь проверок: уязвимости зависимостей (Python и Node), небезопасные паттерны
в коде (bandit, semgrep), секреты (gitleaks), CVE и мисконфиги файловой системы
(trivy fs), лучшие практики Dockerfile (hadolint), плюс опционально CVE
собранных образов (trivy image).

Политика (SPEC_SFR4b §2):
  * High/Critical — падение;
  * Medium/Low — строка в логе, но не падение;
  * CVE базовых образов **без доступного фикса** не валят прогон: чинить их
    нечем, кроме ожидания апстрима. Строгий режим — `--fail-unfixed`.

Инструменты Python живут в dev-группе `security` (uv), бинарные — берутся из
PATH, а если их там нет — из официального docker-образа с запиненным тегом.
Нет ни того ни другого — шаг помечается SKIP с понятным сообщением, а не
роняет прогон: локальная машина без docker всё равно должна прогонять
остальное. В CI все инструменты есть, поэтому SKIP там означает дефект job'а
и с `--strict` считается падением.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMGREP_RULES = ROOT / "security" / "semgrep"

# Версии запинены: обновление сканера — осознанный шаг (новые правила = новые
# находки), а не случайный красный CI в понедельник. Совпадают с CI-workflow.
DOCKER_IMAGES = {
    "gitleaks": "ghcr.io/gitleaks/gitleaks:v8.30.1",
    "trivy": "aquasec/trivy:0.74.0",
    "hadolint": "hadolint/hadolint:v2.15.1",
}

# Образы, которые сканирует `trivy image`, если они собраны локально.
LOCAL_IMAGES = ("sfr-api:latest", "sfr-web:latest", "sfr-proxy:latest")

DOCKERFILES = ("apps/api/Dockerfile", "apps/web/Dockerfile", "deploy/proxy/Dockerfile")

OK, FAIL, WARN, SKIP = "OK", "FAIL", "WARN", "SKIP"

PY_TOOL_HINT = (
    "{tool} не найден — запускай через `make audit` "
    "(он поднимает uv-группу security), а не голым python"
)


@dataclass
class Result:
    """Итог одного шага аудита."""

    name: str
    status: str
    note: str = ""


def run(cmd: Sequence[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    """Запустить команду в корне репозитория, вернув текстовый результат."""
    return subprocess.run(
        list(cmd), cwd=ROOT, text=True, check=False, capture_output=capture_output
    )


def echo(cmd: Sequence[str]) -> None:
    print(f"\n$ {' '.join(cmd)}", flush=True)


# ---------------------------------------------------------------------------
# Разрешение бинарных инструментов: PATH -> docker -> нет
# ---------------------------------------------------------------------------


def binary(tool: str, *, docker_args: Sequence[str] = ()) -> list[str] | None:
    """Команда для запуска бинарного сканера или None, если запустить нечем."""
    local = shutil.which(tool)
    if local:
        return [local]
    if shutil.which("docker") is None:
        return None
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{ROOT}:/work",
        "-w",
        "/work",
        *docker_args,
        DOCKER_IMAGES[tool],
    ]


def missing(tool: str) -> str:
    return (
        f"нет ни {tool} в PATH, ни docker для {DOCKER_IMAGES[tool]}; "
        f"поставь один из них — шаг пропущен"
    )


# ---------------------------------------------------------------------------
# Зависимости
# ---------------------------------------------------------------------------


def export_requirements(dest: Path, *, groups: bool) -> None:
    """Выгрузить залоченные версии в requirements.txt для pip-audit.

    pip-audit не умеет читать uv.lock, поэтому идём через `uv export`. Две
    правки над экспортом:
      * маркеры окружения отбрасываются — аудит должен покрывать и linux-ветку
        резолва, а не только текущую платформу;
      * локальный сегмент версии (`torch==2.13.0+cpu` из индекса pytorch-cpu)
        срезается: на PyPI такой версии нет и pip-audit не смог бы её найти,
        а исходники там те же, что у `2.13.0`.
    """
    cmd = ["uv", "export", "--format", "requirements-txt", "--no-hashes", "--no-emit-workspace"]
    cmd += ["--all-packages", "--all-groups" if groups else "--no-dev"]
    proc = run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"uv export упал: {proc.stderr.strip()[:400]}")

    pinned: dict[str, str] = {}
    for raw in proc.stdout.splitlines():
        line = raw.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        match = re.match(r"^([A-Za-z0-9._-]+)==(\S+)$", line.split(";")[0].strip())
        if match:
            name, version = match.group(1), match.group(2).split("+")[0]
            pinned[name.lower()] = f"{name}=={version}"
    dest.write_text("\n".join(sorted(pinned.values())) + "\n", encoding="utf-8")


def step_pip_audit(tmp: Path, *, groups: bool) -> Result:
    label = "deps-python (dev+security)" if groups else "deps-python (runtime)"
    req = tmp / ("req-all.txt" if groups else "req-runtime.txt")
    try:
        export_requirements(req, groups=groups)
    except RuntimeError as exc:
        return Result(label, SKIP, str(exc))
    count = len(req.read_text(encoding="utf-8").strip().splitlines())
    if shutil.which("pip-audit") is None:
        return Result(label, SKIP, PY_TOOL_HINT.format(tool="pip-audit"))
    cmd = ["pip-audit", "-r", str(req), "--no-deps", "--disable-pip"]
    echo(cmd)
    proc = run(cmd)
    note = f"{count} пакетов"
    return Result(label, OK if proc.returncode == 0 else FAIL, note)


def step_npm_audit() -> Result:
    web = ROOT / "apps" / "web"
    if shutil.which("npm") is None:
        return Result("deps-node", SKIP, "нет npm в PATH")
    if not (web / "node_modules").exists():
        return Result("deps-node", SKIP, "нет apps/web/node_modules — сделай make web-setup")
    cmd = ["npm", "audit", "--audit-level=high"]
    echo(cmd)
    proc = subprocess.run(cmd, cwd=web, text=True, check=False)
    return Result("deps-node", OK if proc.returncode == 0 else FAIL, "apps/web")


# ---------------------------------------------------------------------------
# Код
# ---------------------------------------------------------------------------


def step_bandit() -> Result:
    # -ll: Low отсекается. В Low попадает `assert` в тестах (434 штуки) —
    # шум, который утопил бы настоящие находки.
    if shutil.which("bandit") is None:
        return Result("code-bandit", SKIP, PY_TOOL_HINT.format(tool="bandit"))
    cmd = ["bandit", "-r", "packages", "apps/api", "-ll", "-q"]
    echo(cmd)
    proc = run(cmd)
    return Result("code-bandit", OK if proc.returncode == 0 else FAIL, "packages + apps/api")


def step_semgrep(tmp: Path) -> Result:
    packs = sorted(SEMGREP_RULES.glob("*.yaml"))
    if not packs:
        return Result("code-semgrep", SKIP, f"нет правил в {SEMGREP_RULES} — см. fetch-rules.sh")
    out = tmp / "semgrep.json"
    if shutil.which("semgrep") is None:
        return Result("code-semgrep", SKIP, PY_TOOL_HINT.format(tool="semgrep"))
    cmd = ["semgrep", "scan", "--metrics=off", "--quiet"]
    for pack in packs:
        cmd += ["--config", str(pack.relative_to(ROOT))]
    # Правила лежат в репозитории, и сканировать их самими собой бессмысленно:
    # в паке secrets по определению есть образцы ключей.
    cmd += ["--exclude", "security/semgrep"]
    cmd += ["--json", "--output", str(out), "."]
    echo(cmd)
    proc = run(cmd)
    if not out.exists():
        return Result("code-semgrep", FAIL, f"semgrep не отдал отчёт (код {proc.returncode})")

    report = json.loads(out.read_text(encoding="utf-8"))
    findings = report.get("results", [])
    by_severity = Counter(f["extra"]["severity"] for f in findings)
    for finding in findings:
        extra = finding["extra"]
        print(
            f"  [{extra['severity']}] {finding['check_id']}\n"
            f"      {finding['path']}:{finding['start']['line']} — "
            f"{extra['message'].strip().splitlines()[0][:140]}"
        )
    scanned = len(report.get("paths", {}).get("scanned", []))
    note = f"{scanned} файлов, {len(findings)} находок"
    if findings:
        note += f" {dict(by_severity)}"
    if by_severity.get("ERROR"):
        return Result("code-semgrep", FAIL, note)
    return Result("code-semgrep", WARN if findings else OK, note)


# ---------------------------------------------------------------------------
# Секреты
# ---------------------------------------------------------------------------


def step_gitleaks(mode: str) -> Result:
    label = f"secrets-gitleaks ({mode})"
    # gitleaks в контейнере работает от root, а .git принадлежит хостовому
    # пользователю: без safe.directory git ругается на «dubious ownership».
    docker_args = (
        "-e",
        "GIT_CONFIG_COUNT=1",
        "-e",
        "GIT_CONFIG_KEY_0=safe.directory",
        "-e",
        "GIT_CONFIG_VALUE_0=/work",
    )
    cmd = binary("gitleaks", docker_args=docker_args)
    if cmd is None:
        return Result(label, SKIP, missing("gitleaks"))
    cmd = [*cmd, mode, ".", "--redact", "--no-banner"]
    if mode == "git":
        # Вся история, включая ветки и объекты вне текущего HEAD.
        cmd.append("--log-opts=--all --full-history")
    echo(cmd)
    proc = run(cmd)
    note = "рабочее дерево" if mode == "dir" else "вся история git"
    return Result(label, OK if proc.returncode == 0 else FAIL, note)


# ---------------------------------------------------------------------------
# Trivy
# ---------------------------------------------------------------------------

TRIVY_SKIP_DIRS = (".venv", "node_modules", "data", "_to_delete", ".next", ".git")


def trivy_ignorefile() -> list[str]:
    """Передать trivy файл исключений явно, если он заведён."""
    for name in (".trivyignore.yaml", ".trivyignore"):
        if (ROOT / name).exists():
            return ["--ignorefile", name]
    return []


def trivy_cmd(*, docker_socket: bool = False) -> list[str] | None:
    cache = Path.home() / ".cache" / "trivy"
    cache.mkdir(parents=True, exist_ok=True)
    args = ["-v", f"{cache}:/root/.cache/trivy"]
    if docker_socket:
        args += ["-v", "/var/run/docker.sock:/var/run/docker.sock"]
    return binary("trivy", docker_args=args)


def parse_trivy(path: Path) -> tuple[list[str], list[str]]:
    """Разобрать JSON trivy: (находки с доступным фиксом, находки без фикса)."""
    report = json.loads(path.read_text(encoding="utf-8"))
    fixable: list[str] = []
    unfixed: list[str] = []
    for result in report.get("Results") or []:
        target = result.get("Target", "?")
        for vuln in result.get("Vulnerabilities") or []:
            line = (
                f"{target}: {vuln['PkgName']} {vuln.get('InstalledVersion', '?')} "
                f"{vuln['VulnerabilityID']} ({vuln['Severity']})"
            )
            if vuln.get("FixedVersion"):
                fixable.append(f"{line} -> {vuln['FixedVersion']}")
            else:
                unfixed.append(line)
        for mis in result.get("Misconfigurations") or []:
            fixable.append(f"{target}: {mis['ID']} ({mis['Severity']}) {mis['Title']}")
    return fixable, unfixed


def report_trivy(label: str, path: Path, *, fail_unfixed: bool) -> Result:
    fixable, unfixed = parse_trivy(path)
    for line in fixable:
        print(f"  [фикс есть] {line}")
    if unfixed:
        print(f"  [без фикса в апстриме] {len(unfixed)} шт.:")
        for line in unfixed[:5]:
            print(f"      {line}")
        if len(unfixed) > 5:
            print(f"      … ещё {len(unfixed) - 5}")
    note = f"с фиксом: {len(fixable)}, без фикса: {len(unfixed)}"
    if fixable or (fail_unfixed and unfixed):
        return Result(label, FAIL, note)
    return Result(label, WARN if unfixed else OK, note)


def step_trivy_fs(tmp: Path, *, fail_unfixed: bool) -> Result:
    cmd = trivy_cmd()
    if cmd is None:
        return Result("fs-trivy", SKIP, missing("trivy"))
    out = tmp / "trivy-fs.json"
    cmd = [
        *cmd,
        "fs",
        "--severity",
        "HIGH,CRITICAL",
        # Секреты закрывает gitleaks, дублировать детекторы незачем.
        "--scanners",
        "vuln,misconfig",
        "--no-progress",
        *trivy_ignorefile(),
        "-f",
        "json",
        "-o",
        f"/work/{out.relative_to(ROOT)}" if cmd[0] == "docker" else str(out),
    ]
    for skip in TRIVY_SKIP_DIRS:
        cmd += ["--skip-dirs", skip]
    cmd.append(".")
    echo(cmd)
    proc = run(cmd)
    if not out.exists():
        return Result("fs-trivy", FAIL, f"trivy не отдал отчёт (код {proc.returncode})")
    return report_trivy("fs-trivy", out, fail_unfixed=fail_unfixed)


def step_trivy_images(tmp: Path, *, fail_unfixed: bool) -> list[Result]:
    if shutil.which("docker") is None:
        return [Result("image-trivy", SKIP, "нет docker — образы не собраны и не сканируются")]
    known = run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True)
    present = set(known.stdout.split())
    results: list[Result] = []
    for image in LOCAL_IMAGES:
        label = f"image-trivy {image.split(':')[0]}"
        if image not in present:
            results.append(Result(label, SKIP, f"образ {image} не собран локально"))
            continue
        cmd = trivy_cmd(docker_socket=True)
        if cmd is None:
            results.append(Result(label, SKIP, missing("trivy")))
            continue
        out = tmp / f"trivy-{image.replace(':', '-').replace('/', '-')}.json"
        target = f"/work/{out.relative_to(ROOT)}" if cmd[0] == "docker" else str(out)
        cmd = [
            *cmd,
            "image",
            "--severity",
            "HIGH,CRITICAL",
            "--scanners",
            "vuln",
            "--no-progress",
            *trivy_ignorefile(),
            "-f",
            "json",
            "-o",
            target,
            image,
        ]
        echo(cmd)
        proc = run(cmd)
        if not out.exists():
            results.append(Result(label, FAIL, f"trivy не отдал отчёт (код {proc.returncode})"))
            continue
        results.append(report_trivy(label, out, fail_unfixed=fail_unfixed))
    return results


# ---------------------------------------------------------------------------
# Hadolint
# ---------------------------------------------------------------------------


def step_hadolint() -> Result:
    cmd = binary("hadolint")
    if cmd is None:
        return Result("dockerfile-hadolint", SKIP, missing("hadolint"))
    if cmd[0] == "docker":
        cmd = [*cmd, "hadolint"]
    # error валит прогон, warning/info печатаются. Точечные исключения живут
    # инлайном в Dockerfile (`# hadolint ignore=DLxxxx` + причина рядом).
    cmd = [*cmd, "--failure-threshold", "error", *DOCKERFILES]
    echo(cmd)
    proc = run(cmd)
    return Result(
        "dockerfile-hadolint",
        OK if proc.returncode == 0 else FAIL,
        f"{len(DOCKERFILES)} Dockerfile",
    )


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Аудит безопасности Search For Research")
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="не сканировать собранные образы (режим CI: там их нет)",
    )
    parser.add_argument(
        "--fail-unfixed",
        action="store_true",
        help="валить прогон и на CVE без доступного фикса",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="считать SKIP падением (в CI инструменты обязаны быть)",
    )
    args = parser.parse_args()

    results: list[Result] = []
    with tempfile.TemporaryDirectory(dir=ROOT, prefix=".audit-") as raw_tmp:
        tmp = Path(raw_tmp)
        results.append(step_pip_audit(tmp, groups=False))
        results.append(step_pip_audit(tmp, groups=True))
        results.append(step_npm_audit())
        results.append(step_bandit())
        results.append(step_semgrep(tmp))
        results.append(step_gitleaks("dir"))
        results.append(step_gitleaks("git"))
        results.append(step_trivy_fs(tmp, fail_unfixed=args.fail_unfixed))
        results.append(step_hadolint())
        if not args.no_images:
            results.extend(step_trivy_images(tmp, fail_unfixed=args.fail_unfixed))

    width = max(len(r.name) for r in results)
    print("\n" + "=" * (width + 40))
    print("Аудит безопасности (SFR-4b)")
    print("=" * (width + 40))
    for result in results:
        print(f"  {result.status:<5} {result.name:<{width}}  {result.note}")
    print("=" * (width + 40))

    failed = [r for r in results if r.status == FAIL]
    skipped = [r for r in results if r.status == SKIP]
    if args.strict and skipped:
        failed += skipped
    if failed:
        print(f"\nПадение: {', '.join(r.name for r in failed)}")
        print("Как читать и что делать — docs/SECURITY_CI.md")
        return 1
    print("\nВсё чисто" + (f" (пропущено: {len(skipped)})" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
