"""Слепые парные карточки и неизменяемые фактические ответы человека.

Только локальные файлы; агентская оценка не является человеческой разметкой.
"""

import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from enrichment_experiment import FIELDS, private_root, read, sha, write_new
from enrichment_human import assessed_date_summary, esc, field_label, label, proof
from enrichment_semantics import validate
from enrichment_verification import identifier, immutable_bytes

GRADES = {
    "correct": "Корректно",
    "incorrect": "Некорректно",
    "insufficient": "Недостаточно данных для решения",
}
AXES = {
    "identity": "Связь с человеком",
    "current_affiliation": "Нынешняя аффилиация",
    "activity": "Профессиональная активность",
}
SELF_IDENTIFICATION = re.compile(
    r"\b(?:glm(?:[- ]?5)?|codex|z[.]?ai|gpt[- ]?\d|pi\s+agent)\b", re.I
)


def _save(path: Path, value: Any) -> None:
    if path.exists():
        if read(path) != value:
            raise ValueError("Существующая запись отличается")
    else:
        write_new(path, value)


def _response(source: dict[str, Any], path: Path, digest: str) -> dict[str, Any]:
    wrapper = read(path)
    result = wrapper.get("result", wrapper)
    try:
        derived = validate(source, result, digest)
    except ValueError as exc:
        if wrapper.get("validation") != {"succeeded": False, "errors": [str(exc)]}:
            raise
        derived = None
    if "input_sha256" in wrapper and wrapper["input_sha256"] != digest:
        raise ValueError("Обёртка связана с другим входом")
    if "classifications" in wrapper and wrapper["classifications"] != derived:
        raise ValueError("Производная классификация отличается")
    # Provenance, runtime and paths belong only to the separate unblinding file.
    response = {key: result[key] for key in ("items", "profile_assessments", "summary")}
    response["validation"] = wrapper.get("validation", {"succeeded": True, "errors": []})
    narratives = [*response["summary"].values()]
    for row in [*response["items"], *response["profile_assessments"].values()]:
        narratives.extend(row.get(key, "") for key in ("explanation", "question", "value_ru"))
    if any(SELF_IDENTIFICATION.search(text) for text in narratives):
        raise ValueError("Ответ раскрывает исполнителя; исходник сохранён, слепой пакет не создан")
    return response


def generate(root: Path, packet_id: str, entries: list[dict[str, Any]], blind_seed: str) -> Path:
    """entries: input_path, result_paths={pi,native}, selection_reason; максимум три."""
    root = private_root(root)
    identifier(packet_id)
    if not 1 <= len(entries) <= 3 or not isinstance(blind_seed, str) or not blind_seed:
        raise ValueError("Нужны 1–3 профиля и непустой seed")
    profiles, mapping, questions = [], [], []
    seen = set()
    for entry in entries:
        source_path = Path(entry["input_path"])
        source = read(source_path)
        author = identifier(source["author_id"])
        if author in seen or not str(entry.get("selection_reason", "")).strip():
            raise ValueError("Повторный профиль или отсутствует причина отбора")
        seen.add(author)
        paths = entry["result_paths"]
        if set(paths) != {"pi", "native"}:
            raise ValueError("Нужны ровно два независимых результата")
        digest = sha(source_path)
        results = {name: _response(source, Path(path), digest) for name, path in paths.items()}
        agents = [
            read(Path(path)).get("result", read(Path(path)))["provenance"]["agent_id"]
            for path in paths.values()
        ]
        if len(set(agents)) != 2:
            raise ValueError("Исполнители должны быть независимыми")
        order = ["pi", "native"]
        if hashlib.sha256(f"{blind_seed}:{author}".encode()).digest()[0] % 2:
            order.reverse()
        answers = dict(zip(("A", "B"), (results[name] for name in order), strict=True))
        profiles.append(
            {
                "author_id": author,
                "profile": source["profile"],
                "items": source["items"],
                "evidence_pool": source["evidence_pool"],
                "responses": answers,
                "input_sha256": digest,
                "selection_reason": entry["selection_reason"],
                "field_statuses": source.get("field_statuses", {}),
                "collector_quoted_fragments": source.get("collector_quoted_fragments", {}),
            }
        )
        mapping.append(
            {
                "author_id": author,
                "input_path": str(source_path),
                "input_sha256": digest,
                "responses": {
                    slot: {
                        "executor": name,
                        "result_path": str(paths[name]),
                        "result_sha256": sha(Path(paths[name])),
                    }
                    for slot, name in zip(("A", "B"), order, strict=True)
                },
            }
        )
        for slot in answers:
            for question in [
                "summary",
                *("axis:" + axis for axis in AXES),
                *("item:" + row["item_id"] for row in source["items"]),
            ]:
                questions.append({"author_id": author, "response": slot, "question_id": question})
    manifest = {
        "schema": "paired_human_packet_v1",
        "packet_id": packet_id,
        "profiles": profiles,
        "questions": questions,
        "human_reviewed": False,
    }
    directory = root / "paired-human" / "packets" / packet_id
    manifest_path = directory / "manifest.json"
    _save(manifest_path, manifest)
    _save(
        root / "paired-human" / "unblinding" / f"{packet_id}.json",
        {
            "packet_id": packet_id,
            "packet_sha256": sha(manifest_path),
            "blind_seed": blind_seed,
            "profiles": mapping,
        },
    )
    page = _page(manifest, sha(manifest_path))
    immutable_bytes(directory / "cards.html", page.encode())
    return directory / "cards.html"


def _grade(author: str, slot: str, question: str) -> str:
    key = esc(json.dumps([author, slot, question], ensure_ascii=False))
    options = "".join(f'<option value="{code}">{text}</option>' for code, text in GRADES.items())
    return (
        f'<label>Ваша оценка ответа {slot}: <select data-key="{key}">'
        f'<option value="">Не просмотрено</option>{options}</select></label>'
        f'<label>Комментарий <textarea data-note="{key}"></textarea></label>'
    )


def _page(manifest: dict[str, Any], digest: str) -> str:
    cards = []
    for profile in manifest["profiles"]:
        author, pool = profile["author_id"], profile["evidence_pool"]
        cards.append(
            f"<article><h2>{esc(profile['profile'].get('name', author))}</h2>"
            f"<p>Организация каталога: {esc(profile['profile'].get('institution'))}.</p>"
            f"<p>Причина отбора: {esc(profile['selection_reason'])}.</p>"
            "<p>Оба ответа проверяют одинаковый сохранённый набор. Совпадение ответов "
            "не доказывает их правильность. Полнота свежего поиска отдельно не проверена.</p>"
        )
        missing_fields = [
            field_label(field)
            for field in FIELDS
            if field not in {item["original_field"] for item in profile["items"]}
        ]
        if missing_fields:
            cards.append(
                "<p><strong>Сборщик не сохранил утверждений для полей:</strong> "
                + esc(", ".join(missing_fields))
                + ". Отсутствие утверждения не означает отсутствие сведений. "
                "Вопрос человеку: видны ли пропущенные сведения в сохранённых источниках?</p>"
            )
        statuses = {
            "found": "Есть утверждение сборщика (ещё не принято)",
            "not_found": "Не найдено в ограниченном поиске",
            "not_checked": "Не проверено",
            "inaccessible": "Источник недоступен",
            "contradiction": "Противоречие",
            "explicit_negative": "Явное отрицание",
        }
        if profile["field_statuses"]:
            cards.append("<details><summary>Состояние полей по ответу сборщика</summary><table>")
            for field, status in profile["field_statuses"].items():
                cards.append(
                    f"<tr><td>{esc(field_label(field))}</td>"
                    f"<td>{esc(statuses.get(status, 'Неизвестно'))}</td></tr>"
                )
            cards.append("</table></details>")
        cards.append(
            "<details><summary>Все сохранённые фрагменты общего пакета</summary>"
            + proof(list(pool.values()))
            + "</details>"
        )
        original_quotes = profile.get("collector_quoted_fragments", {})
        if original_quotes:
            cards.append(
                "<details><summary>Исходные цитаты сборщика (могут содержать ошибки)</summary>"
                + proof([dict(row, checked_at=None) for row in original_quotes.values()])
                + "</details>"
            )
        for slot, response in profile["responses"].items():
            cards.append(f"<section><h3>Краткий ответ {slot}</h3>")
            if not response["validation"]["succeeded"]:
                cards.append(
                    "<p><strong>Ответ не прошёл автоматическую проверку; "
                    "его утверждения не приняты.</strong> "
                    + esc("; ".join(response["validation"]["errors"]))
                    + "</p>"
                )
            for key, title in {
                "known": "Что известно",
                "unknown": "Что неизвестно",
                "identity": "Связь с человеком",
                "current_opportunity": "Актуальность возможности",
            }.items():
                cards.append(f"<p><strong>{title}:</strong> {esc(response['summary'][key])}</p>")
            cards.append(
                "<p>Вопрос: корректен ли этот вывод по сохранённым материалам?</p>"
                + _grade(author, slot, "summary")
                + "</section>"
            )
        for axis, title in AXES.items():
            cards.append(f"<section><h3>{title}</h3>")
            for slot, response in profile["responses"].items():
                row = response["profile_assessments"][axis]
                if axis == "activity":
                    cards.append(f"<p>Статус в ответе {slot}: {label(row.get('status'))}.</p>")
                cards.append(
                    f"<h4>Ответ {slot}</h4><p>{label(row['verdict'])}. "
                    f"{esc(row['explanation'])}</p>"
                    + assessed_date_summary(row)
                    + proof([pool[key] for key in row["evidence_refs"]])
                    + "<p>Вопрос: установлено ли это именно для данного человека?</p>"
                    + _grade(author, slot, "axis:" + axis)
                )
            cards.append("</section>")
        if not profile["items"]:
            cards.append(
                "<p>Сборщик не сохранил положительных полевых утверждений. "
                "Это не доказательство отсутствия сведений или набора.</p>"
            )
        for item in profile["items"]:
            cards.append(
                f"<section><h3>{esc(field_label(item['original_field']))}</h3>"
                f"<p><strong>Утверждение сборщика:</strong> {esc(item.get('value'))}</p>"
                + proof([pool[key] for key in item["evidence_refs"]])
            )
            for slot, response in profile["responses"].items():
                row = next(row for row in response["items"] if row["item_id"] == item["item_id"])
                levels = ", ".join(label(level) for level in row["student_level"])
                cards.append(
                    f"<h4>Ответ {slot}</h4><p>Текст: {label(row['text_verdict'])}. "
                    f"Личность: {label(row['identity_verdict'])}. "
                    f"Смысл поля: {label(row['field_verdict'])}. "
                    f"Объект: {label(row['object_type'])}. "
                    f"Связь объекта: {label(row['object_relation'])}. "
                    f"Уровень студента: {esc(levels)}. "
                    f"Актуальность: {label(row['current_applicability'])}.</p>"
                    f"<p>{esc(row['explanation'])}</p>" + assessed_date_summary(row)
                )
                if row.get("corrected_field"):
                    cards.append(
                        f"<p>Предлагаемое поле: {esc(field_label(row['corrected_field']))}.</p>"
                    )
                cards.append(
                    proof([pool[key] for key in row["evidence_refs"]])
                    + f"<p><strong>Вопрос человеку:</strong> {esc(row['question'])}</p>"
                    + _grade(author, slot, "item:" + item["item_id"])
                )
            cards.append("</section>")
        cards.append("</article>")
    config = json.dumps(
        {
            "schema": "paired_human_answers_v1",
            "packet_id": manifest["packet_id"],
            "packet_sha256": digest,
        },
        ensure_ascii=False,
    ).replace("<", "\\u003c")
    return (
        """<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Парная проверка материалов</title>
<style>
body{font:17px/1.5 system-ui;max-width:1000px;margin:2rem auto;padding:1rem}
article,section{border:1px solid #ddd;padding:1rem;margin:1rem 0}
blockquote{white-space:pre-wrap;border-left:3px solid #ccc;padding:1rem}
label{display:block;margin:.5rem 0}textarea{width:95%}
select,input{font:inherit}h4{color:#245}
</style>
<h1>Фактический просмотр человеком</h1>
<p>Вы можете признать оба ответа некорректными или недостаточно обоснованными.
Оставленные пустыми решения не считаются просмотром.
Исходные цитаты не переведены и не заменены пересказом.</p>
<label>Ваше имя <input id="human-name"></label>
<label>Фактически затрачено минут
<input id="minutes" type="number" min="0.01" step="0.01"></label>
<label><input id="attestation" type="checkbox">
Я лично просмотрел материалы отмеченных ответов</label>"""
        + "".join(cards)
        + """<button id="save">Сохранить мои решения в JSON</button>
<p id="message"></p><script>
const config="""
        + config
        + """;
document.getElementById('save').onclick=()=>{
 const name=document.getElementById('human-name').value.trim();
 const minutes=Number(document.getElementById('minutes').value);
 const message=document.getElementById('message');
 if(!name||!Number.isFinite(minutes)||minutes<=0||
    !document.getElementById('attestation').checked){
  message.textContent='Укажите имя, фактическое время и подтвердите личный просмотр.';
  return;
 }
 const answers=[];
 document.querySelectorAll('select[data-key]').forEach(el=>{
  if(!el.value)return;
  const [author_id,response,question_id]=JSON.parse(el.dataset.key);
  const note=Array.from(document.querySelectorAll('textarea[data-note]'))
    .find(t=>t.dataset.note===el.dataset.key).value;
  answers.push({author_id,response,question_id,grade:el.value,note});
 });
 if(!answers.length){message.textContent='Не отмечено ни одного ответа.';return;}
 const value={...config,human_name:name,minutes,actual_human_attestation:true,
   reviewed_at:new Date().toISOString(),answers};
 const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],
   {type:'application/json'}));
 const a=document.createElement('a');a.href=url;
 a.download=config.packet_id+'-answers.json';a.click();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
};
</script></html>"""
    )


def import_answers(root: Path, manifest_path: Path, answers_path: Path) -> Path:
    """Только импорт реально заполненных решений; повторный импорт не создаёт дубль."""
    root = private_root(root)
    manifest, value = read(manifest_path), read(answers_path)
    if (
        manifest.get("schema") != "paired_human_packet_v1"
        or value.get("schema") != "paired_human_answers_v1"
    ):
        raise ValueError("Другая схема")
    if value.get("packet_id") != manifest["packet_id"] or value.get("packet_sha256") != sha(
        manifest_path
    ):
        raise ValueError("Ответы относятся к другому пакету")
    if (
        value.get("actual_human_attestation") is not True
        or not isinstance(value.get("human_name"), str)
        or not value["human_name"].strip()
    ):
        raise ValueError("Нужны имя и подтверждение реального личного просмотра")
    minutes = value.get("minutes")
    if (
        isinstance(minutes, bool)
        or not isinstance(minutes, int | float)
        or not math.isfinite(minutes)
        or minutes <= 0
    ):
        raise ValueError("Нужно фактическое положительное время")
    reviewed = datetime.fromisoformat(value.get("reviewed_at", "").replace("Z", "+00:00"))
    if reviewed.tzinfo is None:
        raise ValueError("Нужна дата просмотра с часовым поясом")
    expected = {(q["author_id"], q["response"], q["question_id"]) for q in manifest["questions"]}
    actual = set()
    rows = value.get("answers")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Нет фактических решений")
    for row in rows:
        key = (row.get("author_id"), row.get("response"), row.get("question_id"))
        if (
            key not in expected
            or key in actual
            or row.get("grade") not in GRADES
            or not isinstance(row.get("note", ""), str)
        ):
            raise ValueError("Повторный, чужой или некорректный ответ")
        actual.add(key)
    complete = [
        p["author_id"]
        for p in manifest["profiles"]
        if {key for key in expected if key[0] == p["author_id"]} <= actual
    ]
    record = {
        "schema": "paired_human_record_v1",
        "answers_sha256": sha(answers_path),
        "answers": value,
        "fully_reviewed_profiles": complete,
        "reviewed_responses": len(actual),
        "total_responses": len(expected),
    }
    destination = (
        root / "paired-human" / "records" / f"{manifest['packet_id']}-{sha(answers_path)}.json"
    )
    _save(destination, record)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    packet = sub.add_parser("generate")
    packet.add_argument("--packet-id", required=True)
    packet.add_argument("--entries", required=True, type=Path)
    packet.add_argument("--blind-seed", required=True)
    answers = sub.add_parser("import-answers")
    answers.add_argument("--manifest", required=True, type=Path)
    answers.add_argument("--answers", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "generate":
        print(generate(args.root, args.packet_id, read(args.entries), args.blind_seed))
    else:
        print(import_answers(args.root, args.manifest, args.answers))


if __name__ == "__main__":
    main()
