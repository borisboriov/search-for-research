"""Файловый адаптер независимой проверки и пакетов человеческого просмотра.

Не запускает API и не принимает агентский вердикт за человеческую оценку.
Все персональные входы/выходы сохраняются исключительно вне git.
"""

import argparse
import html
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from enrichment_experiment import (
    FIELDS,
    STATUSES,
    private_root,
    read,
    sha,
    verified_sample,
    write_new,
)

VERDICTS = ("confirmed_by_source", "refuted", "insufficient_evidence", "sources_conflict")
OBJECTS = ("scientist", "laboratory", "organization", "offer")


LABELS = dict(
    zip(
        FIELDS,
        (
            "Личный контакт",
            "Контакт координатора",
            "История руководства",
            "Опубликованный набор",
            "Прямая готовность",
            "Тема",
            "Роль руководителя",
            "Уровень студента",
            "Курс студента",
            "Необходимые навыки",
            "Внешние студенты",
            "Возможность ВКР",
            "Город",
            "Формат",
            "Нагрузка",
            "Оплата",
            "Срок отклика",
            "Как откликнуться",
        ),
        strict=True,
    )
)
TRANSLATIONS = {
    "found": "Найдено",
    "not_found": "Не найдено в пределах поиска",
    "not_checked": "Не проверено",
    "inaccessible": "Недоступность / неопределённость",
    "contradiction": "Противоречие",
    "explicit_negative": "Явное отрицание",
    "confirmed_by_source": "Подтверждено источником",
    "refuted": "Опровергнуто",
    "insufficient_evidence": "Недостаточно оснований",
    "sources_conflict": "Источники противоречат",
}


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Небезопасный идентификатор пути")
    return value


def evidence(items: Any, required: bool = True) -> None:
    if not isinstance(items, list) or (required and not items):
        raise ValueError("Нужны подтверждающие фрагменты")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Некорректное доказательство")
        for key in ("url", "excerpt", "checked_at", "explanation"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"Пустое доказательство: {key}")
        if urlparse(item["url"]).scheme not in ("https", "http"):
            raise ValueError("Доказательство должно ссылаться на HTTP(S)")
        if item.get("object_type") not in OBJECTS or "information_date" not in item:
            raise ValueError("Нужны объект и дата сведений (может быть неизвестна)")
        if item["information_date"] is not None and not isinstance(item["information_date"], str):
            raise ValueError("Некорректная дата сведений")


def journal_check(rows: Any) -> None:
    if not isinstance(rows, list):
        raise ValueError("Журнал должен быть списком")
    counts = {"search": 0, "page": 0}
    for row in rows:
        kind = row.get("kind")
        if kind not in counts:
            raise ValueError("Неизвестная операция журнала")
        counts[kind] += 1
        for key in ("checked_at", "status", "query" if kind == "search" else "url"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError(f"Неполная запись журнала: {key}")
        for key in ("elapsed_seconds", "cost_usd"):
            value = row.get(key)
            if value is not None and (not isinstance(value, int | float) or value < 0):
                raise ValueError(f"Некорректный расход: {key}")
            if key not in row:
                raise ValueError(f"Неизвестный расход должен быть явно null: {key}")
    if counts["search"] > 4 or counts["page"] > 8:
        raise ValueError("Превышен бюджет 4 поиска / 8 страниц на профиль")


def collector_check(row: dict[str, Any]) -> None:
    identifier(row["author_id"])
    if set(row["field_status"]) != set(FIELDS):
        raise ValueError("Нужны статусы всех 18 полей")
    if any(status not in STATUSES for status in row["field_status"].values()):
        raise ValueError("Неизвестный статус поля")
    ids = []
    for claim in row["claims"]:
        ids.append(identifier(claim["claim_id"]))
        if claim["field"] not in FIELDS or "value" not in claim:
            raise ValueError("Неизвестное поле утверждения")
        if any(key in claim for key in ("verdict", "expected_verdict")):
            raise ValueError("Вход не должен содержать ожидаемый вердикт")
        evidence(claim["evidence"])
    if len(ids) != len(set(ids)):
        raise ValueError("Повторный claim_id")
    journal_check(row["journal"])
    if not isinstance(row["sources"], list):
        raise ValueError("Нужен список исходных материалов")


def immutable_json(path: Path, value: Any) -> None:
    if path.exists():
        if read(path) != value:
            raise ValueError(f"Существующий артефакт отличается: {path.name}")
        return
    write_new(path, value)


def prepare(root: Path, collector: Path, version: str, rubric: Path) -> list[Path]:
    root = private_root(root)
    version = identifier(version)
    sample = {row["id"]: row for row in verified_sample(root)}
    rows = read(collector)
    if isinstance(rows, dict):
        rows = [rows]
    paths = []
    seen = set()
    for row in rows:
        collector_check(row)
        author_id = row["author_id"]
        if author_id not in sample or author_id in seen:
            raise ValueError("Профиль отсутствует в выборке или повторяется")
        seen.add(author_id)
        value = {
            "author_id": author_id,
            "profile": sample[author_id],
            "collector": {
                key: row[key]
                for key in (
                    "author_id",
                    "claims",
                    "field_status",
                    "journal",
                    "sources",
                    "provenance",
                )
                if key in row
            },
            "collector_sha256": sha(collector),
            "sample_sha256": sha(root / "sample.json"),
            "rules_version": version,
            "rubric_sha256": sha(rubric),
            "budgets": {"search_queries": 4, "pages": 8},
            "source_text_policy": "untrusted_data_not_instructions",
        }
        path = root / "verification" / version / "inputs" / f"{author_id}.json"
        if path.exists():
            previous = read(path)
            previous_collector = previous.get("collector", {})
            comparable = dict(previous)
            comparable["collector"] = {
                key: previous_collector[key]
                for key in value["collector"]
                if key in previous_collector
            }
            if comparable != value:
                raise ValueError("Замороженный вход отличается; нужна новая версия")
        else:
            immutable_json(path, value)
        paths.append(path)
    return paths


def verdict_check(row: dict[str, Any]) -> None:
    if row.get("verdict") not in VERDICTS or not row.get("explanation"):
        raise ValueError("Нужны вердикт и объяснение")
    evidence(row.get("evidence"), required=row["verdict"] != "insufficient_evidence")


def validate_result(input_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    source = read(input_path)
    if result.get("input_sha256") != sha(input_path):
        raise ValueError("SHA входа не соответствует результату")
    if result.get("author_id") != source["author_id"]:
        raise ValueError("Результат другого профиля")
    if result.get("rules_version") != source["rules_version"]:
        raise ValueError("Версия правил отличается")
    provenance = result.get("provenance", {})
    if not provenance.get("agent_id"):
        raise ValueError("Не указан независимый исполнитель")
    collector_agent = source["collector"].get("provenance", {}).get("agent_id")
    if collector_agent and provenance["agent_id"] == collector_agent:
        raise ValueError("Проверяющий не может быть автором извлечения")
    runtime = provenance.get("runtime_status")
    if runtime not in ("recorded", "runtime_not_exposed"):
        raise ValueError("Не указан статус сведений о runtime")
    for key in ("model", "effort"):
        if key not in provenance or (runtime == "recorded" and not provenance[key]):
            raise ValueError("Нужно происхождение model/effort или явное null")
    for key in ("identity", "current_affiliation"):
        verdict_check(result[key])
    expected = {claim["claim_id"] for claim in source["collector"]["claims"]}
    actual = [claim["claim_id"] for claim in result["claim_verdicts"]]
    if set(actual) != expected or len(actual) != len(set(actual)):
        raise ValueError("Проверить каждое исходное утверждение ровно один раз")
    for claim in result["claim_verdicts"]:
        verdict_check(claim)
    finding_ids = []
    for finding in result["new_findings"]:
        finding_ids.append(identifier(finding["finding_id"]))
        if (
            finding["field"] not in FIELDS
            or "value" not in finding
            or not finding.get("explanation")
        ):
            raise ValueError("Некорректная новая находка")
        evidence(finding["evidence"])
    if len(finding_ids) != len(set(finding_ids)):
        raise ValueError("Повторная новая находка")
    if set(result["field_search"]) != set(FIELDS):
        raise ValueError("Нужен поиск пропусков по всем 18 полям")
    for field in result["field_search"].values():
        if field.get("status") not in STATUSES or not field.get("explanation"):
            raise ValueError("Нужны статус и основание поиска пропусков")
    journal_check(result["journal"])
    if not isinstance(result.get("questions"), list):
        raise ValueError("Нужен список спорных вопросов")
    return dict(source)


def import_result(root: Path, input_path: Path, result_path: Path, run_id: str) -> Path:
    root = private_root(root)
    source = read(input_path)
    # Повторно проверяем неизменность выборки перед каждой загрузкой результата.
    frozen = {row["id"]: row for row in verified_sample(root)}
    if source.get("profile") != frozen.get(source.get("author_id")):
        raise ValueError("Профиль входа отличается от замороженного")
    if source.get("sample_sha256") != sha(root / "sample.json"):
        raise ValueError("Вход относится к другой выборке")
    result = read(result_path)
    validate_result(input_path, result)
    path = (
        root
        / "verification"
        / identifier(source["rules_version"])
        / "outputs"
        / identifier(run_id)
        / f"{identifier(result['author_id'])}.json"
    )
    immutable_json(
        path,
        {
            "input_sha256": sha(input_path),
            "result_sha256": sha(result_path),
            "result": result,
            "human_reviewed": False,
            "human_verdict": None,
            "human_minutes": None,
            "accepted_automatically": False,
        },
    )
    return path


def escaped(value: Any) -> str:
    return html.escape(str(value), quote=True)


def evidence_html(items: list[dict[str, Any]]) -> str:
    chunks = []
    for item in items:
        evidence([item])
        chunks.append(
            f'<p><a href="{escaped(item["url"])}">Источник</a> · '
            f"{escaped(item['object_type'])} · дата сведений: "
            f"{escaped(item['information_date'] or 'неизвестна')} · "
            f"проверено: {escaped(item['checked_at'])}<br>"
            f"<q>{escaped(item['excerpt'])}</q><br>{escaped(item['explanation'])}</p>"
        )
    return "".join(chunks)


def packet(root: Path, inputs: Path, run_id: str, ids: list[str], name: str) -> Path:
    root = private_root(root)
    if not 1 <= len(ids) <= 5 or len(ids) != len(set(ids)):
        raise ValueError("Пакет содержит от одного до пяти уникальных профилей")
    cards, summaries, fingerprints = [], [], []
    for author_id in ids:
        identifier(author_id)
        inp = inputs / f"{author_id}.json"
        source = read(inp)
        out = inputs.parent / "outputs" / identifier(run_id) / f"{author_id}.json"
        wrapper = read(out)
        result = wrapper["result"]
        validate_result(inp, result)
        fingerprints.append(
            {"author_id": author_id, "input_sha256": sha(inp), "output_sha256": sha(out)}
        )
        profile = source["profile"]
        title = f"{profile.get('name', author_id)} — {profile.get('institution', '')}"
        card = [
            f"<article><h2>{escaped(title)}</h2><p>{escaped(author_id)} · "
            "Просмотр человеком: нет · вердикт: не заполнен · время: не заполнено</p>"
            f"<p>h-index: {escaped(profile.get('h_index', 'не указан'))} · "
            f"Темы каталога: {escaped('; '.join(profile.get('topics', [])))}</p>"
        ]
        summaries.append(f"## {title}\n\nID: {author_id}. Человек: не просмотрено.\n")
        provenance = result["provenance"]
        card.append(
            f"<p>Правила: {escaped(source['rules_version'])} · запуск: {escaped(run_id)} · "
            f"агент: {escaped(provenance['agent_id'])} · "
            f"модель: {escaped(provenance['model'] or 'не раскрыта runtime')} · "
            f"effort: {escaped(provenance['effort'] or 'не раскрыт runtime')}</p>"
        )

        for key, label in (
            ("identity", "Личность"),
            ("current_affiliation", "Нынешняя аффилиация"),
        ):
            row = result[key]
            card.append(
                f"<h3>{label}: {escaped(TRANSLATIONS[row['verdict']])}</h3>"
                f"<p>{escaped(row['explanation'])}</p>"
            )
            card.append(evidence_html(row["evidence"]))
            summaries.append(f"{label}: {row['verdict']}. {row['explanation']}\n")
        card.append(
            "<h3>Поля и поиск пропусков</h3><table><tr><th>Поле</th>"
            "<th>Сборщик</th><th>Проверяющий</th><th>Основание</th></tr>"
        )
        for field in FIELDS:
            search = result["field_search"][field]
            card.append(
                f"<tr><td>{escaped(LABELS[field])}</td><td>{escaped(TRANSLATIONS[source['collector']['field_status'][field]])}</td>"
                f"<td>{escaped(TRANSLATIONS[search['status']])}</td>"
                f"<td>{escaped(search['explanation'])}</td></tr>"
            )
            summaries.append(
                f"- {field}: сборщик {source['collector']['field_status'][field]}, "
                f"проверяющий {search['status']}: {search['explanation']}\n"
            )
        card.append("</table><h3>Утверждения сборщика и проверка</h3>")
        verdicts = {item["claim_id"]: item for item in result["claim_verdicts"]}
        for claim in source["collector"]["claims"]:
            verdict = verdicts[claim["claim_id"]]
            card.append(
                f"<h4>{escaped(claim['claim_id'])} · {escaped(LABELS[claim['field']])}</h4>"
                f"<p>{escaped(claim['value'])}</p>"
            )
            card.append(evidence_html(claim["evidence"]))
            card.append(
                f"<p>Проверяющий: {escaped(TRANSLATIONS[verdict['verdict']])} · "
                f"{escaped(verdict['explanation'])}</p>"
            )
            card.append(evidence_html(verdict["evidence"]))
            summaries.append(
                f"\nУтверждение {claim['claim_id']} ({claim['field']}): {claim['value']}\n"
                f"\nВердикт: {verdict['verdict']}. {verdict['explanation']}\n"
            )
            for item in claim["evidence"] + verdict["evidence"]:
                summaries.append(
                    f"\nИсточник: {item['url']}\n\n> {item['excerpt']}\n"
                    f"\nДата сведений: {item['information_date']}; "
                    f"проверка: {item['checked_at']}.\n"
                )
        card.append("<h3>Новые находки / пропуски</h3>")
        for finding in result["new_findings"]:
            card.append(
                f"<p>{escaped(LABELS[finding['field']])}: {escaped(finding['value'])} · "
                f"{escaped(finding['explanation'])}</p>"
            )
            card.append(evidence_html(finding["evidence"]))
            summaries.append(
                f"\nНовая находка {finding['field']}: {finding['value']}. "
                f"{finding['explanation']}\n"
            )
            for item in finding["evidence"]:
                summaries.append(f"\n{item['url']}\n\n> {item['excerpt']}\n")
        card.append("<h3>Вопросы человеку</h3><ul>")
        for question in source["collector"].get("questions", []) + result["questions"]:
            card.append(f"<li>{escaped(question)}</li>")
            summaries.append(f"\nВопрос человеку: {question}\n")
        card.append("</ul></article>")
        cards.append("".join(card))
    directory = (
        root / "verification" / identifier(source["rules_version"]) / "packets" / identifier(name)
    )
    immutable_json(directory / "manifest.json", {"profiles": fingerprints, "human_reviewed": False})
    body = (
        '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Проверка профилей</title>'
        "<style>body{font:16px system-ui;max-width:1100px;margin:2em auto;padding:1em}"
        "article{border-bottom:2px solid #777;padding:1em 0}"
        "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:.4em}"
        "q{white-space:pre-wrap}a{overflow-wrap:anywhere}</style>"
        "<h1>Пакет человеческого просмотра</h1>"
        "<p>Агентская проверка не является человеческим эталоном. "
        "Спорные утверждения автоматически не приняты.</p>" + "".join(cards) + "</html>"
    )
    for path, content in (
        (directory / "review.html", body),
        (directory / "review.md", html.escape("\n".join(summaries), quote=False)),
    ):
        if path.exists():
            if path.read_text() != content:
                raise ValueError("Пакет изменился; нужен новый name")
        else:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
    return directory / "review.html"


def metrics(root: Path, version: str, run_id: str, out: Path) -> dict[str, Any]:
    """Только белый список агрегатов; нулевая human-проверка не означает нулевую ошибку."""
    sample = verified_sample(root)
    manifest = read(root / "manifest.json")
    directory = root / "verification" / identifier(version)
    inputs = {p.stem: read(p) for p in (directory / "inputs").glob("*.json")}
    outputs = {}
    for path in (directory / "outputs" / identifier(run_id)).glob("*.json"):
        wrapper = read(path)
        result = wrapper["result"]
        validate_result(directory / "inputs" / f"{path.stem}.json", result)
        if wrapper.get("human_reviewed"):
            raise ValueError("Агентский агрегатор не оценивает человеческие результаты")
        outputs[path.stem] = result
    cohort_counts = {}
    for cohort in ("pilot", "evaluation"):
        ids = set(manifest.get(f"{cohort}_ids", []))
        cohort_counts[cohort] = {
            "frozen": len(ids),
            "inputs": len(ids & inputs.keys()),
            "outputs": len(ids & outputs.keys()),
        }
    field_counts = {}
    all_verdicts: Counter[str] = Counter()
    identity: Counter[str] = Counter()
    affiliation: Counter[str] = Counter()
    omissions: Counter[str] = Counter()
    fresh: Counter[str] = Counter()
    collector_log = []
    verifier_log = []
    for field in FIELDS:
        original_profiles = set()
        new_profiles = set()
        original_claims = 0
        new_claims = 0
        for author_id, result in outputs.items():
            claims = {c["claim_id"]: c for c in inputs[author_id]["collector"]["claims"]}
            for verdict in result["claim_verdicts"]:
                if (
                    claims[verdict["claim_id"]]["field"] == field
                    and verdict["verdict"] == "confirmed_by_source"
                ):
                    original_profiles.add(author_id)
                    original_claims += 1
            findings = [f for f in result["new_findings"] if f["field"] == field]
            if findings:
                new_profiles.add(author_id)
                new_claims += len(findings)
        field_counts[field] = {
            "collector_found_profiles": sum(
                r["collector"]["field_status"][field] == "found" for r in inputs.values()
            ),
            "verifier_confirmed_original_profiles": len(original_profiles),
            "verifier_confirmed_original_claims": original_claims,
            "verifier_new_finding_profiles": len(new_profiles),
            "verifier_new_findings": new_claims,
            "verifier_combined_profiles": len(original_profiles | new_profiles),
        }
    for source in inputs.values():
        collector_log.extend(source["collector"]["journal"])
    for result in outputs.values():
        verifier_log.extend(result["journal"])
        identity[result["identity"]["verdict"]] += 1
        affiliation[result["current_affiliation"]["verdict"]] += 1
        for verdict in result["claim_verdicts"]:
            all_verdicts[verdict["verdict"]] += 1
        for finding in result["new_findings"]:
            omissions[finding["field"]] += 1
        for row in [
            result["identity"],
            result["current_affiliation"],
            *result["claim_verdicts"],
            *result["new_findings"],
        ]:
            for item in row["evidence"]:
                fresh[
                    "dated_evidence" if item["information_date"] else "unknown_date_evidence"
                ] += 1

    def costs(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "search_queries": sum(row["kind"] == "search" for row in rows),
            "pages": sum(row["kind"] == "page" for row in rows),
            "access_failures": sum(
                row["status"] in ("inaccessible", "blocked", "error", "failed", "timeout")
                for row in rows
            ),
            "cost_usd_known_sum": sum(
                row["cost_usd"] for row in rows if row["cost_usd"] is not None
            ),
            "cost_usd_unknown_count": sum(row["cost_usd"] is None for row in rows),
            "elapsed_seconds_known_sum": sum(
                row["elapsed_seconds"] for row in rows if row["elapsed_seconds"] is not None
            ),
            "elapsed_seconds_unknown_count": sum(row["elapsed_seconds"] is None for row in rows),
        }

    value = {
        "method_version": identifier(version),
        "denominators": {
            "sample": len(sample),
            "inputs": len(inputs),
            "outputs": len(outputs),
            "human_reviewed": 0,
            **cohort_counts,
        },
        "fields": field_counts,
        "claim_verdicts": dict(all_verdicts),
        "identity_verdicts": dict(identity),
        "current_affiliation_verdicts": dict(affiliation),
        "omissions": dict(omissions),
        "freshness": dict(fresh),
        "collector_operations": costs(collector_log),
        "verifier_operations": costs(verifier_log),
        "human_claim_error_rate": None,
        "human_identity_error_rate": None,
        "human_verifier_disagreement_rate": None,
        "human_review_minutes": None,
        "disputed_automatically_accepted": 0,
    }
    immutable_json(out, value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--root", type=Path, required=True)
    prep.add_argument("--collector", type=Path, required=True)
    prep.add_argument("--version", required=True)
    prep.add_argument("--rubric", type=Path, required=True)
    imp = commands.add_parser("import")
    imp.add_argument("--root", type=Path, required=True)
    imp.add_argument("--input", type=Path, required=True)
    imp.add_argument("--result", type=Path, required=True)
    imp.add_argument("--run-id", required=True)
    pack = commands.add_parser("packet")
    pack.add_argument("--root", type=Path, required=True)
    pack.add_argument("--inputs", type=Path, required=True)
    pack.add_argument("--run-id", required=True)
    pack.add_argument("--ids", nargs="+", required=True)
    pack.add_argument("--name", required=True)
    met = commands.add_parser("metrics")
    met.add_argument("--root", type=Path, required=True)
    met.add_argument("--version", required=True)
    met.add_argument("--run-id", required=True)
    met.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result: Any = [
            str(path) for path in prepare(args.root, args.collector, args.version, args.rubric)
        ]
    elif args.command == "import":
        result = str(import_result(args.root, args.input, args.result, args.run_id))
    elif args.command == "metrics":
        result = metrics(args.root, args.version, args.run_id, args.out)
    else:
        result = str(packet(args.root, args.inputs, args.run_id, args.ids, args.name))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
