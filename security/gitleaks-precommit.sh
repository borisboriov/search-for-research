#!/usr/bin/env bash
# gitleaks на staged-изменениях (pre-commit, SFR-4b).
#
# Официальный хук gitleaks собирается из исходников (language: golang) — на
# машине без Go это долгая сборка на каждом `pre-commit install`. Здесь та же
# логика, что в scripts/audit.py: берём бинарь из PATH, иначе запускаем
# запиненный docker-образ. Нет ни того ни другого — предупреждаем и пропускаем:
# коммит блокировать нечем, но молчать об этом нельзя.
#
# Тяжёлые сканеры (semgrep, trivy) в pre-commit сознательно не ставим — они
# минуты, а хук должен быть секунды. Их место — `make audit` и CI.
set -uo pipefail

IMAGE="ghcr.io/gitleaks/gitleaks:v8.30.1"
REPO_ROOT="$(git rev-parse --show-toplevel)"

if command -v gitleaks >/dev/null 2>&1; then
    exec gitleaks git "$REPO_ROOT" --staged --redact --no-banner
fi

if command -v docker >/dev/null 2>&1; then
    exec docker run --rm \
        -v "$REPO_ROOT:/work" -w /work \
        -e GIT_CONFIG_COUNT=1 \
        -e GIT_CONFIG_KEY_0=safe.directory \
        -e GIT_CONFIG_VALUE_0=/work \
        "$IMAGE" git . --staged --redact --no-banner
fi

echo "gitleaks: пропущено — нет ни gitleaks в PATH, ни docker для $IMAGE." >&2
echo "          Секреты в этом коммите не проверены. brew install gitleaks." >&2
exit 0
