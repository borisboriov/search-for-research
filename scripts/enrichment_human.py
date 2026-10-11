"""Локальные русские карточки и отдельные фактические решения человека.

Не выполняет сетевых запросов и не меняет исходные агентские результаты.
"""

import argparse
import html
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from enrichment_experiment import private_root, read, sha, write_new
from enrichment_verification import LABELS, identifier, immutable_bytes

WORDS = {
    "confirmed_by_source": "Подтверждено текстом источника",
    "refuted": "Опровергнуто",
    "insufficient_evidence": "Недостаточно оснований",
    "sources_conflict": "Источники противоречат",
    "confirmed": "Установлено",
    "supported": "Подтверждено",
    "insufficient": "Недостаточно оснований",
    "conflicting": "Источники противоречат",
    "expired": "Срок предложения истёк",
    "undated": "Дата неизвестна",
    "explicit_negative": "Опубликовано явное отрицание",
    "undergraduate": "Бакалавриат",
    "masters": "Магистратура",
    "phd": "Аспирантура / PhD",
    "postdoc": "Постдок",
    "correct": "Соответствует полю",
    "appropriate": "Соответствует полю",
    "misclassified": "Неверно отнесено к полю",
    "reclassified": "Классификация исправлена",
    "unknown": "Не установлено",
    "not_established": "Не установлено",
    "current": "Подтверждена текущая применимость",
    "historical": "Исторические сведения",
    "closed": "Предложение закрыто",
    "active": "Подтверждена профессиональная активность",
    "deceased": "Есть подтверждение смерти",
    "ceased": "Есть подтверждение прекращения работы",
    "scientist": "Человек",
    "laboratory": "Лаборатория",
    "organization": "Организация",
    "offer": "Предложение",
    "random": "Случайная выборка",
    "targeted": "Целевой отбор",
    "corrected": "Спорные случаи после исправлений",
}
DIMENSIONS = {
    "text": "Подтверждение текстом",
    "identity": "Связь с человеком",
    "field": "Смысл поля",
    "object": "Объект утверждения",
    "current": "Актуальность",
    "source_date": "Дата источника",
}
CONTACT_AXES = ("text", "identity", "source_date", "current")
DECISIONS = {"agree": "Согласен", "disagree": "Не согласен", "uncertain": "Недостаточно оснований"}
DATE_BASES = {
    "content": "Указана в содержании источника",
    "source_metadata": "Подтверждена метаданными источника",
    "url_only": "Есть только дата в адресе страницы; дата сведений не установлена",
    "conflicting": "Даты противоречат друг другу; дата сведений не установлена",
    "unknown": "Основание даты не установлено",
}


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else "Неизвестно"), quote=True)


def label(value: Any) -> str:
    if value is None:
        return "Не установлено"
    return WORDS.get(str(value), "Не установлено")


def field_label(value: Any) -> str:
    return LABELS.get(
        str(value),
        {
            "appointment_duration": "Длительность договора",
            "nationality": "Гражданство",
            "person_status": "Статус человека",
        }.get(str(value), "Другое сведение"),
    )


EXCLUSION_REASONS = {
    "additional_field_not_original_coverage": "Это дополнительная категория, а не исходное поле.",
    "new_finding_candidate_not_independently_confirmed": (
        "Новая находка остаётся кандидатом без независимого подтверждения."
    ),
    "text_verdict": "Текст недостаточно подтверждает факт.",
    "identity_verdict": "Связь факта с этим человеком не установлена.",
    "field_verdict": "Факт неверно классифицирован или принадлежность полю не установлена.",
    "object_relation": "Не установлена связь нужного объекта с человеком.",
    "workload_requires_effort_not_duration": (
        "Срок договора или обучения не означает рабочую нагрузку."
    ),
    "external_requires_institutional_membership": (
        "Гражданство не подтверждает допуск студента из другого вуза."
    ),
    "field_requires_matching_fact_kind": "Вид факта не соответствует смыслу поля.",
    "personal_willingness_requires_scientist": (
        "Готовность организации не подтверждает личную готовность учёного."
    ),
    "negative_not_positive_coverage": "Явное отрицание не учитывается как положительный результат.",
    "opportunity_not_current": "Текущая применимость возможности не установлена.",
    "current_opportunity_date_unestablished": "Дата текущей возможности не подтверждена.",
    "student_opportunity_not_established": (
        "Позиция постдока или неизвестный уровень не доказывает возможность для студента."
    ),
}


def coverage_explanation(assessment: dict[str, Any]) -> str:
    eligibility = assessment.get("eligibility")
    if not isinstance(eligibility, dict):
        return "Пригодность для покрытия поля отдельно не установлена."
    if eligibility.get("usable_coverage"):
        return "Учитывается в покрытии поля после проверки смысла и принадлежности."
    reasons = eligibility.get("reason", [])
    explanations = [
        EXCLUSION_REASONS.get(reason, "Недостаточно оснований для покрытия поля.")
        for reason in reasons
    ]
    return "Не увеличивает положительное покрытие поля. " + " ".join(explanations)


def assessed_date_summary(assessment: dict[str, Any]) -> str:
    basis = assessment.get("date_basis")
    # URL, conflicting dates and a reading date cannot establish a fact's date.
    date = assessment.get("information_date") if basis in ("content", "source_metadata") else None
    return (
        "<p><strong>Дата сведений по оценке проверяющего:</strong> "
        f"{esc(date)}. <strong>Основание даты:</strong> "
        f"{esc(DATE_BASES.get(str(basis), DATE_BASES['unknown']))}. "
        "Дата чтения страницы не обновляет эти сведения.</p>"
    )


def profile_axis_summary(name: str, assessment: dict[str, Any]) -> str:
    axis = assessment.get("profile_assessments", {}).get(name, {})
    title = {
        "activity": "Профессиональная активность",
        "current_affiliation": "Нынешняя аффилиация",
    }[name]
    status = label(axis.get("status")) if name == "activity" else label(axis.get("verdict"))
    return (
        f"<p><strong>{title}:</strong> {status}. "
        f"{esc(axis.get('explanation'))}. "
        "Это отдельная оценка; она не подтверждает нынешний набор.</p>"
        + assessed_date_summary(axis)
    )


def proof(rows: list[dict[str, Any]], *, show_url: bool = False) -> str:
    parts = []
    for row in rows:
        url = str(row.get("url", ""))
        link = (
            f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
            f"{esc(url) if show_url else 'Первоисточник'}</a>"
            if urlparse(url).scheme in ("http", "https")
            else "Ссылка недоступна"
        )
        parts.append(
            f'<div class="proof">{link}'
            + (
                f"<details><summary>Полный сохранённый контекст "
                f"({len(str(row.get('excerpt', '')))} символов)</summary>"
                if show_url and len(str(row.get("excerpt", ""))) > 1600
                else ""
            )
            + f"<blockquote>{esc(row.get('excerpt'))}</blockquote>"
            + ("</details>" if show_url and len(str(row.get("excerpt", ""))) > 1600 else "")
            + f"<p>Дата в исходных метаданных: "
            f"{esc(row.get('information_date'))}. Дата проверки источника: "
            f"{esc(row.get('checked_at'))}. Эти даты сами по себе не подтверждают "
            "дату факта или текущую применимость.</p></div>"
        )
    return "".join(parts) or "<p>Подтверждающий фрагмент не сохранён.</p>"


def assessment_rows(assessment: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = assessment.get("claim_assessments", [])
    return rows


def contact_source_date(assessment: dict[str, Any]) -> str:
    """Датированность источника отдельно от доказательства нынешней применимости."""
    date = (
        assessment.get("information_date")
        if assessment.get("date_basis") in ("content", "source_metadata")
        else None
    )
    text = "Есть дата: " + str(date) if date else "Без установленной даты"
    if assessment.get("current_applicability") == "historical":
        text += "; исторический источник"
    return text


def normalize(
    source: dict[str, Any], wrapper: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Приводит v3 к структуре отображения, сохраняя все исходные оси решения."""
    if "items" not in source:
        return source, wrapper
    from enrichment_semantics import validate

    result = wrapper["result"]
    derived = validate(source, result, wrapper["input_sha256"])
    if derived != wrapper["classifications"]:
        raise ValueError("Производная классификация отличается")
    pool = source["evidence_pool"]
    originals = []
    assessments = []
    findings = []
    decisions = {item["item_id"]: item for item in result["items"]}
    if len(decisions) != len(result["items"]) or set(decisions) != {
        item["item_id"] for item in source["items"]
    }:
        raise ValueError("Не все атомарные утверждения получили ровно одну оценку")
    for item in source["items"]:
        original = dict(
            item,
            claim_id=item["item_id"],
            field=item["original_field"],
            evidence=[pool[key] for key in item["evidence_refs"]],
        )
        assessed = dict(
            decisions[item["item_id"]],
            claim_id=item["item_id"],
            human_question=decisions[item["item_id"]]["question"],
            evidence=[pool[key] for key in decisions[item["item_id"]]["evidence_refs"]],
        )
        assessed["eligibility"] = wrapper.get("classifications", {}).get(item["item_id"])
        originals.append(original)
        assessments.append(assessed)
        if item["origin"] == "verifier_candidate":
            findings.append(original)
    normalized_source = dict(source, collector={"claims": originals})
    normalized_result = dict(
        result,
        claim_assessments=assessments,
        identity=result["profile_assessments"]["identity"],
        new_findings=findings,
    )
    return normalized_source, normalized_result


def make_packet(
    root: Path, packet_id: str, entries: list[dict[str, Any]], *, contact_review: bool = False
) -> Path:
    """Каждая entry: input_path, assessment_path, stratum, selection_reason."""
    root = private_root(root)
    identifier(packet_id)
    if not 1 <= len(entries) <= (10 if contact_review else 5):
        raise ValueError("Пакет превышает лимит профилей: 10 для контактов, 5 для общего обзора")
    profiles = []
    seen = set()
    for entry in entries:
        source_path = Path(entry["input_path"])
        assessed_path = Path(entry["assessment_path"])
        source, assessment = read(source_path), read(assessed_path)
        author_id = identifier(source["author_id"])
        result = assessment.get("result", assessment)
        if author_id in seen or result["author_id"] != author_id:
            raise ValueError("Повторный профиль или чужая оценка")
        seen.add(author_id)
        if assessment.get("input_sha256", result.get("input_sha256")) != sha(source_path):
            raise ValueError("Оценка связана с другим входом")
        if (
            entry["stratum"] not in ("random", "targeted", "corrected", "pilot")
            or not entry["selection_reason"]
        ):
            raise ValueError("Нужны группа и сохранённая причина отбора")
        source, assessment = normalize(source, assessment)
        originals = {c["claim_id"]: c for c in source["collector"]["claims"]}
        assessed_all = assessment_rows(assessment)
        if len(assessed_all) != len(originals) or {a["claim_id"] for a in assessed_all} != set(
            originals
        ):
            raise ValueError("Нужна оценка каждого исходного утверждения")
        selected = entry.get("review_claim_ids")
        if contact_review:
            if (
                not isinstance(selected, list)
                or any(not isinstance(key, str) for key in selected)
                or len(selected) != len(set(selected))
                or not set(selected) <= originals.keys()
            ):
                raise ValueError("Нужен явный список выбранных контактных утверждений")
            by_id = {a["claim_id"]: a for a in assessed_all}
            if any(
                originals[key]["field"] != "personal_contact"
                or not by_id[key].get("eligibility", {}).get("usable_coverage")
                or by_id[key]["eligibility"]["coverage_field"] != "personal_contact"
                for key in selected
            ):
                raise ValueError("Выбран не принятый личный контакт")
        profiles.append(
            {
                "author_id": author_id,
                "profile": source["profile"],
                "collector": source["collector"],
                "assessment": assessment,
                "input_sha256": sha(source_path),
                "assessment_sha256": sha(assessed_path),
                "stratum": entry["stratum"],
                "selection_reason": entry["selection_reason"],
                **({"review_claim_ids": selected} if contact_review else {}),
            }
        )
    manifest = {
        "schema": "human_packet_v4" if contact_review else "human_packet_v3",
        "packet_id": packet_id,
        "profiles": profiles,
        "human_reviewed": False,
        **({"review_scope": "selected_personal_contacts"} if contact_review else {}),
    }
    directory = root / ("human-v4" if contact_review else "human-v3") / "packets" / packet_id
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        if read(manifest_path) != manifest:
            raise ValueError("Существующий пакет отличается")
    else:
        write_new(manifest_path, manifest)
    digest = sha(manifest_path)
    cards = []
    questions = []
    for profile in profiles:
        assessment = profile["assessment"]
        identity = assessment.get("identity", {})
        identity_status = identity.get("verdict") if isinstance(identity, dict) else identity
        cards.append(
            f'<article id="profile-{esc(profile["author_id"])}"><h2>'
            f"{esc(profile['profile'].get('name', profile['author_id']))}</h2>"
            f"<p>ID: {esc(profile['author_id'])}. Организация в исходном каталоге: "
            f"{esc(profile['profile'].get('institution'))}.</p><p>"
            f"<strong>Связь материалов с человеком:</strong> "
            f"{label(identity_status)}. Актуальность возможности "
            f"оценивается отдельно для каждого утверждения; наличие "
            f"контакта не означает набор.</p><p>"
            f"{label(profile['stratum'])}. Причина отбора: "
            f"{esc(profile['selection_reason'])}.</p>"
        )
        summary = assessment.get("summary", {})
        cards.append(
            "<p><strong>Что известно:</strong> "
            + esc(summary.get("known"))
            + "</p><p><strong>Что неизвестно:</strong> "
            + esc(summary.get("unknown"))
            + "</p><p><strong>Связь с человеком:</strong> "
            + esc(summary.get("identity"))
            + "</p><p><strong>Актуальность возможности:</strong> "
            + esc(summary.get("current_opportunity"))
            + "</p>"
        )
        cards.append(profile_axis_summary("activity", assessment))
        cards.append(profile_axis_summary("current_affiliation", assessment))
        original = {c["claim_id"]: c for c in profile["collector"]["claims"]}
        if contact_review and not profile["review_claim_ids"]:
            cards.append(
                "<p><strong>Личный контакт по этим сохранённым материалам не установлен.</strong> "
                "Это отсутствие принятого контакта, а не доказательство, что контакта нет. "
                "Ответ о принадлежности не требуется: принятый контакт не предъявлен.</p>"
                "<details><summary>Почему кандидаты не приняты</summary>"
            )
            for assessed in assessment_rows(assessment):
                claim = original[assessed["claim_id"]]
                cards.append(
                    "<p>"
                    + esc(assessed.get("explanation"))
                    + "</p>"
                    + proof(claim.get("evidence", []), show_url=True)
                )
            cards.append("</details>")
        for assessed in assessment_rows(assessment):
            if contact_review and assessed["claim_id"] not in profile["review_claim_ids"]:
                continue
            claim = original[assessed["claim_id"]]
            identifier(claim["claim_id"])
            key = f"{profile['author_id']}:{claim['claim_id']}"
            corrected = assessed.get("corrected_field")
            levels = ", ".join(label(level) for level in assessed.get("student_level", ["unknown"]))
            options = "".join(
                f"<option value={code}>{text}</option>" for code, text in DECISIONS.items()
            )
            question = assessed.get("human_question") or (
                "Подтверждает ли источник это сведение именно для указанного человека "
                f"и поля «{field_label(corrected or claim['field'])}» "
                "с указанной актуальностью?"
            )
            if contact_review:
                # Вопрос native может быть обращён владельцу адреса и просить подтвердить
                # доставляемость. Человек здесь оценивает только приведённые доказательства.
                question = (
                    "Оцените приведённый контакт по четырём вопросам ниже. "
                    "Если источник не даёт ответа, выберите «Недостаточно оснований». "
                    "Самостоятельно проверять работу адреса не требуется."
                )
            if claim.get("origin") == "verifier_candidate":
                cards.append(
                    "<p><strong>Кандидат: новая находка проверяющего, "
                    "без независимого подтверждения.</strong></p>"
                )
            value_ru = assessed.get("value_ru") or assessed.get("explanation")
            cards.append(
                f"<section><h3>{esc(field_label(claim['field']))}</h3><p>"
                f"<strong>Что проверяем:</strong> {esc(value_ru)}</p>"
                + (
                    f"<p><strong>Контакт:</strong> <code>{esc(claim.get('value'))}</code></p>"
                    if contact_review
                    else ""
                )
                + f"<details><summary>Исходная запись сборщика</summary>"
                f"<p>{esc(claim.get('value'))}</p></details>"
                f"{proof(claim.get('evidence', []), show_url=contact_review)}<p><strong>Решение "
                f"проверяющего:</strong> Текст: "
                f"{label(assessed.get('text_verdict'))}. Личность: "
                f"{label(assessed.get('identity_verdict'))}. Смысл поля: "
                f"{label(assessed.get('field_verdict'))}. Объект: "
                f"{label(assessed.get('object_type'))}. Уровень студента: "
                f"{esc(levels)}. "
                + (
                    "Датированность контактного источника: " + esc(contact_source_date(assessed))
                    if contact_review
                    else "Актуальность: " + label(assessed.get("current_applicability"))
                )
                + ".</p><p>"
                f"{esc(assessed.get('explanation'))}</p>"
            )
            cards.append(assessed_date_summary(assessed))
            cards.append(
                "<p><strong>Учёт в результате:</strong> "
                + esc(coverage_explanation(assessed))
                + "</p>"
            )
            if corrected:
                cards.append(
                    f"<p><strong>Предлагаемое исправление:</strong> "
                    f"{esc(field_label(corrected))}.</p>"
                )
            cards.append(
                f"<details><summary>Доказательства проверяющего</summary>"
                f"{proof(assessed.get('evidence', []))}</details><p>"
                f"<strong>Вопрос человеку:</strong> {esc(question)}</p>"
                f'<label>Ваше решение <select data-key="{esc(key)}">'
                f'<option value="">Не просмотрено</option>'
                f"{options}</select>"
                f"</label><label>Комментарий <textarea "
                f'data-note="{esc(key)}"></textarea></label></section>'
            )
            dimensions = []
            axes = CONTACT_AXES if contact_review else tuple(DIMENSIONS)
            for axis in axes:
                if not contact_review and axis == "source_date":
                    continue
                axis_label = DIMENSIONS[axis]
                axis_question = {
                    "text": "Цитата действительно содержит этот контакт и совпадает с источником?",
                    "identity": "Контакт принадлежит именно указанному учёному?",
                    "source_date": (
                        "Согласны с оценкой датированности «"
                        + contact_source_date(assessed)
                        + "» и приведённым основанием даты? Это вопрос о сохранённом источнике."
                    ),
                    "current": (
                        "Есть ли в приведённых источниках основание считать контакт актуальным "
                        "сейчас? Если основания нет или вы не знаете, выберите «Недостаточно "
                        "оснований». Проверять адрес письмом или доказывать актуальность не нужно."
                    ),
                }.get(axis, axis_label + ": согласны с решением проверяющего?")
                question_text = (
                    axis_question
                    if contact_review
                    else axis_label + ": согласны с решением проверяющего?"
                )
                dimensions.append(
                    f"<label>{esc(question_text)} "
                    f'<select data-axis="{axis}" data-item="{esc(key)}">'
                    '<option value="not_reviewed">Не проверял это отдельно</option>'
                    + options
                    + "</select></label>"
                )
            corrections = "".join(
                f'<option value="{code}">{esc(text)}</option>'
                for code, text in {
                    **LABELS,
                    "appointment_duration": "Длительность договора",
                    "nationality": "Гражданство",
                    "person_status": "Статус человека",
                }.items()
            )
            cards.append(
                (
                    "<details open><summary>Четыре отдельные проверки контакта</summary>"
                    if contact_review
                    else "<details><summary>Уточнить решение по отдельным вопросам "
                    "или исправить поле</summary>"
                )
                + "".join(dimensions)
                + "<label>Исправить категорию (необязательно) "
                + f'<select data-correction="{esc(key)}">'
                '<option value="">Исправление не записано</option>'
                + corrections
                + "</select></label></details>"
            )
            questions.append(
                {
                    "author_id": profile["author_id"],
                    "claim_id": claim["claim_id"],
                    "original_field": claim["field"],
                    "proposed_field": corrected or claim["field"],
                    "collector_value": claim.get("value"),
                    "verifier_field_verdict": assessed.get("field_verdict"),
                    "stratum": profile["stratum"],
                }
            )
        findings = assessment.get("new_findings", assessment.get("candidate_findings", []))
        cards.append(
            "<details><summary>Новые находки проверяющего — кандидаты, без "
            "независимого подтверждения</summary>"
        )
        for finding in findings:
            cards.append(
                f"<h3>{esc(field_label(finding.get('field')))}</h3><p>"
                f"{esc(finding.get('value'))}</p>"
                f"{proof(finding.get('evidence', []))}"
            )
        cards.append(
            "</details><details><summary>Технические сведения и журнал</summary><pre>"
            + esc(
                json.dumps(
                    {
                        "author_id": profile["author_id"],
                        "input_sha256": profile["input_sha256"],
                        "assessment_sha256": profile["assessment_sha256"],
                        "journal": assessment.get("journal", []),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            + "</pre></details></article>"
        )
    config = (
        json.dumps(
            {
                "schema": "human_answers_v4" if contact_review else "human_answers_v3",
                "packet_id": packet_id,
                "packet_sha256": digest,
                "questions": questions,
                "contact_review": contact_review,
                "required_axes": list(CONTACT_AXES) if contact_review else [],
            },
            ensure_ascii=False,
        )
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    script = """const cfg=JSON.parse(document.getElementById('config').textContent);
document.getElementById('save').onclick=()=>{const name=
document.getElementById('person').value.trim(), minutes=Number(
document.getElementById('minutes').value);
if(!name||
!document.getElementById('attest').checked||
!Number.isFinite(minutes)||
minutes<=0){alert('Укажите имя, фактическое время и подтвердите личный просмотр.');
return;
}const answers=[];
document.querySelectorAll('select[data-key]').forEach(s=>{if(s.value){const q=
cfg.questions.find(q=>
q.author_id+':'+q.claim_id===s.dataset.key);
answers.push({author_id:q.author_id,claim_id:q.claim_id,decision:s.value,note:document.querySelector('textarea[data-note="'+s.dataset.key+'"]').value,
dimensions:Object.fromEntries(Array.from(document.querySelectorAll('select[data-axis]'))
.filter(a=>a.dataset.item===s.dataset.key).map(a=>[a.dataset.axis,a.value])),
corrected_field:document.querySelector('select[data-correction="'+s.dataset.key+'"]').value||null});
}});
if(!answers.length){alert('Запишите хотя бы одно фактическое решение.');
return;
}if(cfg.contact_review&&answers.some(a=>cfg.required_axes.some(k=>
!a.dimensions[k]||a.dimensions[k]==='not_reviewed'))){
alert('Для каждого записанного контакта ответьте отдельно: цитата, принадлежность, '
+'дата источника и актуальность. Можно выбрать «Недостаточно оснований».');return;
}const out={schema:cfg.schema,packet_id:cfg.packet_id,packet_sha256:cfg.packet_sha256,
human_name:name,reviewed_at:new Date().toISOString(),
minutes,actual_human_attestation:true,answers};
const a=document.createElement('a');
a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));
a.download=cfg.packet_id+'-human.json';
a.click();
setTimeout(()=>URL.revokeObjectURL(a.href),1000);
};
"""
    document = (
        (
            '<!doctype html><html lang="ru"><meta charset="utf-8"><title>'
            "Проверка профилей человеком</title><style>"
            "body{font:17px/1.6 system-ui;"
            "max-width:950px;"
            "margin:2em auto;"
            "padding:1em}article{border-top:3px solid #777;"
            "margin-top:2em}section{border:1px solid #bbb;"
            "padding:1em;"
            "margin:1em 0}blockquote{white-space:pre-wrap;"
            "border-left:3px solid #888;"
            "padding-left:1em}textarea{display:block;"
            "width:95%;"
            "min-height:4em}label{display:block;"
            "margin:.6em 0}pre{white-space:pre-wrap;"
            "overflow-wrap:anywhere}details{margin:1em 0}.proof{background:#f4f4f4;"
            "padding:.6em}</style>"
            ""
            "<h1>Проверка профилей человеком</h1><p>Открытие карточки не "
            "считается просмотром. Источники приведены дословно. Запишите "
            "только реально разобранные утверждения; остальные останутся "
            "непроверенными.</p>"
        )
        + (
            "<p>Узкая проверка выбранных личных контактов: отдельно подтвердите цитату, "
            "принадлежность человеку, дату источника и наличие оснований актуальности. "
            "Если не знаете — «Недостаточно оснований»: это не подтверждение актуальности. "
            "Публикация email не доказывает доставляемость. Текущий список сотрудников "
            "может подтверждать аффилиацию на дату наблюдения (observed_at); просто живая "
            "персональная страница может содержать старые сведения. Письма и SMTP-проверки "
            "не нужны. Это не проверка набора "
            "студентов и не приёмка остальных утверждений профиля. Перед закрытием "
            "страницы скачайте JSON: автоматического сохранения или отправки нет.</p>"
            if contact_review
            else ""
        )
        + (
            "<nav><strong>Профили:</strong> "
            + " · ".join(
                f'<a href="#profile-{esc(p["author_id"])}">'
                f"{esc(p['profile'].get('name', p['author_id']))}</a>"
                for p in profiles
            )
            + "</nav>"
            if contact_review
            else ""
        )
        + "".join(cards)
        + (
            "<h2>Сохранить фактический просмотр</h2><label>Имя проверившего "
            '<input id="person"></label><label>Фактически затраченные минуты '
            '<input id="minutes" type="number" min="0.1" step="0.1"></label>'
            '<label><input id="attest" type="checkbox"> Я человек и лично '
            "просмотрел источники для записанных решений.</label><button "
            'id="save">Скачать мои решения</button><p>Файл остаётся у вас до '
            "явного импорта. Автоматической отправки нет.</p><script "
            'type="application/json" id="config">'
        )
        + config
        + "</script><script>"
        + script
        + "</script></html>"
    )
    immutable_bytes(directory / "review.html", document.encode())
    return directory / "review.html"


def import_human(root: Path, manifest_path: Path, answers_path: Path, record_id: str) -> Path:
    root = private_root(root)
    identifier(record_id)
    packet, answers = read(manifest_path), read(answers_path)
    version = {"human_packet_v3": "v3", "human_packet_v4": "v4"}.get(packet.get("schema"))
    if (
        version is None
        or (version == "v4" and packet.get("review_scope") != "selected_personal_contacts")
        or answers.get("schema") != "human_answers_" + version
        or answers.get("packet_sha256") != sha(manifest_path)
        or answers.get("packet_id") != packet["packet_id"]
    ):
        raise ValueError("Решения относятся к другому пакету")
    if (
        answers.get("actual_human_attestation") is not True
        or not isinstance(answers.get("human_name"), str)
        or not answers["human_name"].strip()
    ):
        raise ValueError("Нужны имя человека и подтверждение фактического просмотра")
    if (
        not isinstance(answers.get("minutes"), int | float)
        or isinstance(answers["minutes"], bool)
        or not math.isfinite(answers["minutes"])
        or answers["minutes"] <= 0
    ):
        raise ValueError("Нужно фактическое время просмотра")
    datetime.fromisoformat(answers["reviewed_at"].replace("Z", "+00:00"))
    permitted = {
        (p["author_id"], c["claim_id"]): (p, c)
        for p in packet["profiles"]
        for c in p["collector"]["claims"]
        if packet.get("review_scope") != "selected_personal_contacts"
        or c["claim_id"] in p["review_claim_ids"]
    }
    seen = set()
    comparisons = []
    if not answers.get("answers"):
        raise ValueError("Нет фактически просмотренных утверждений")
    for answer in answers["answers"]:
        key = (answer["author_id"], answer["claim_id"])
        if (
            key not in permitted
            or key in seen
            or answer.get("decision") not in DECISIONS
            or not isinstance(answer.get("note"), str)
        ):
            raise ValueError("Неизвестное или повторное утверждение / решение")
        dimensions = answer.get("dimensions", {})
        if not isinstance(dimensions, dict) or any(
            axis not in DIMENSIONS or verdict not in (*DECISIONS, "not_reviewed")
            for axis, verdict in dimensions.items()
        ):
            raise ValueError("Неизвестное решение по отдельному вопросу")
        required_axes = CONTACT_AXES if version == "v4" else ("text", "identity", "current")
        if packet.get("review_scope") == "selected_personal_contacts" and any(
            dimensions.get(axis) not in DECISIONS for axis in required_axes
        ):
            raise ValueError("Для контакта нужны отдельные " + "/".join(required_axes) + " решения")
        correction = answer.get("corrected_field")
        if correction is not None and correction not in (
            *LABELS,
            "appointment_duration",
            "nationality",
            "person_status",
        ):
            raise ValueError("Неизвестное исправленное поле")
        seen.add(key)
        profile, claim = permitted[key]
        assessed = next(
            a for a in assessment_rows(profile["assessment"]) if a["claim_id"] == claim["claim_id"]
        )
        comparisons.append(
            {
                "author_id": key[0],
                "claim_id": key[1],
                "stratum": profile["stratum"],
                "selection_reason": profile["selection_reason"],
                "collector_field": claim["field"],
                "collector_value": claim.get("value"),
                "verifier": assessed,
                "human": answer,
            }
        )
    value = {
        "schema": "human_record_" + version,
        "review_scope": packet.get("review_scope", "all_original_claims"),
        "record_id": record_id,
        "packet_sha256": sha(manifest_path),
        "answers_sha256": sha(answers_path),
        "human": {
            k: answers[k]
            for k in ("human_name", "reviewed_at", "minutes", "actual_human_attestation")
        },
        "comparisons": comparisons,
        "reviewed_claims": len(seen),
        "profile_review": [
            {
                "author_id": p["author_id"],
                "stratum": p["stratum"],
                "reviewed_claims": sum(a == p["author_id"] for a, _ in seen),
                "total_claims": len(p.get("review_claim_ids", p["collector"]["claims"])),
                "total_original_claims": len(p["collector"]["claims"]),
                "all_selected_claims_reviewed": bool(p.get("review_claim_ids"))
                and all((p["author_id"], key) in seen for key in p.get("review_claim_ids", [])),
                "all_original_claims_reviewed": bool(p["collector"]["claims"])
                and all((p["author_id"], c["claim_id"]) in seen for c in p["collector"]["claims"]),
                "human_reviewed": False,
            }
            for p in packet["profiles"]
        ],
    }
    path = root / ("human-" + version) / "records" / f"{record_id}.json"
    write_new(path, value)
    return path


def human_metrics(paths: list[Path]) -> dict[str, Any]:
    strata: dict[str, Counter[str]] = {}
    seen = set()
    eligible: dict[str, dict[str, int]] = {}
    reviewed_profiles: dict[str, set[str]] = {}
    total_minutes = 0.0
    for path in paths:
        record = read(path)
        if (
            record.get("schema") not in ("human_record_v3", "human_record_v4")
            or record["human"]["actual_human_attestation"] is not True
        ):
            raise ValueError("Не фактическая человеческая запись")
        total_minutes += record["human"]["minutes"]
        for profile in record["profile_review"]:
            eligible.setdefault(profile["stratum"], {})[profile["author_id"]] = profile[
                "total_claims"
            ]
        for item in record["comparisons"]:
            key = (record["packet_sha256"], item["author_id"], item["claim_id"])
            if key in seen:
                raise ValueError("Повторные решения нельзя незаметно смешивать")
            seen.add(key)
            reviewed_profiles.setdefault(item["stratum"], set()).add(item["author_id"])
            counter = strata.setdefault(item["stratum"], Counter())
            counter["reviewed_claims"] += 1
            counter[item["human"]["decision"]] += 1
            for axis, decision in item["human"].get("dimensions", {}).items():
                if decision != "not_reviewed":
                    # Старый контактный вопрос смешивал дату и current: не переименовывать
                    # его ответы в новую оценку наличия доказательств актуальности.
                    if (
                        axis == "current"
                        and record["schema"] == "human_record_v3"
                        and record.get("review_scope") == "selected_personal_contacts"
                    ):
                        axis = "legacy_contact_current_v3"
                    counter[f"{axis}_reviewed"] += 1
                    counter[f"{axis}_{decision}"] += 1
            if item["human"].get("corrected_field") is not None:
                counter["human_field_corrections"] += 1
                if item["human"]["corrected_field"] == item["verifier"].get("corrected_field"):
                    counter["human_verifier_same_field_correction"] += 1
    for group, profiles in eligible.items():
        counter = strata.setdefault(group, Counter())
        counter["eligible_profiles"] = len(profiles)
        counter["eligible_claims"] = sum(profiles.values())
        counter["reviewed_profiles"] = len(reviewed_profiles.get(group, set()))
    return {
        "schema": "human_metrics_v3",
        "records": len(paths),
        "actual_human_minutes": total_minutes,
        "strata": strata,
        "quality_without_human_review": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("packet")
    make.add_argument("--root", type=Path, required=True)
    make.add_argument("--entries", type=Path, required=True)
    make.add_argument("--packet-id", required=True)
    ingest = sub.add_parser("import")
    ingest.add_argument("--root", type=Path, required=True)
    ingest.add_argument("--manifest", type=Path, required=True)
    ingest.add_argument("--answers", type=Path, required=True)
    ingest.add_argument("--record-id", required=True)
    args = parser.parse_args()
    if args.command == "packet":
        print(make_packet(args.root, args.packet_id, read(args.entries)))
    else:
        print(import_human(args.root, args.manifest, args.answers, args.record_id))


if __name__ == "__main__":
    main()
