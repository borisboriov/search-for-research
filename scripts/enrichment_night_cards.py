"""Читаемые частные карточки из неизменных результатов; без новых оценок."""

import argparse
import html
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from enrichment_batch import immutable
from enrichment_experiment import private_root, read, verified_sample
from enrichment_night import checked_result
from enrichment_pair_compact import CODES

LABELS = {
    "personal_contact": "Личный профессиональный контакт",
    "coordinator_contact": "Контакт координатора",
    "supervision_history": "Опыт научного руководства",
    "published_recruitment": "Объявление о наборе",
    "direct_willingness": "Личная готовность",
    "topic": "Направления исследований",
    "supervisor_role": "Роль научного руководителя",
    "student_level": "Уровень студента",
    "student_year": "Курс",
    "required_skills": "Требуемые навыки",
    "external_students": "Студенты других вузов",
    "thesis_possible": "Выпускная работа",
    "city": "Город",
    "work_format": "Формат работы",
    "workload": "Нагрузка",
    "payment": "Оплата",
    "deadline": "Срок отклика",
    "response_method": "Как откликнуться",
    "appointment_duration": "Длительность договора",
    "nationality": "Гражданство",
    "person_status": "Профессиональный статус",
}


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def code(value: str) -> str:
    return esc(CODES.get(value, value))


def evidence(source: dict[str, Any], refs: list[str]) -> str:
    blocks = []
    for ref in refs:
        row = source["evidence_pool"][ref]
        url = row["url"]
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username:
            raise ValueError("Неподходящая ссылка в карточке")
        blocks.append(
            f'<section class="quote"><a href="{esc(url)}" target="_blank" '
            'rel="noopener noreferrer">'
            f"{esc(parsed.hostname)} · {esc(ref)}</a>"
            f"<p>Объект: {code(row['object_type'])}. Дата содержания: "
            f"{esc(row['information_date'] or 'не установлена')}. "
            f"Проверено: {esc(row['checked_at'])}.</p>"
            f"<blockquote>{esc(row['excerpt'])}</blockquote></section>"
        )
    return "".join(blocks) or "<p>Сохранённых оснований нет.</p>"


def render(root: Path, output: Path) -> None:
    private_root(output.parent)
    articles = []
    for profile in verified_sample(root):
        aid = profile["id"]
        if not (root / "results" / f"{aid}.json").exists():
            continue
        wrapper = checked_result(root, aid)
        result = wrapper["result"]
        source = read(Path(wrapper["input_path"]))
        axes = []
        for key, label in (
            ("identity", "Личность"),
            ("current_affiliation", "Нынешняя аффилиация"),
            ("activity", "Профессиональная активность"),
        ):
            row = result["profile_assessments"][key]
            status = f" · {code(row['status'])}" if key == "activity" else ""
            axes.append(
                f"<li><b>{label}:</b> {code(row['verdict'])}{status}. "
                f"{esc(row['explanation'])}<details><summary>Сохранённые основания</summary>"
                f"{evidence(source, row['evidence_refs'])}</details></li>"
            )
        established: list[str] = []
        pending: list[str] = []
        for item in source["items"]:
            if item["original_field"] == "topic":
                continue  # Existing catalogue themes are displayed below.
            row = next(value for value in result["items"] if value["item_id"] == item["item_id"])
            derived = wrapper["classifications"][item["item_id"]]
            field = row["corrected_field"] or item["original_field"]
            label = LABELS.get(field, field)
            block = (
                f'<section class="fact"><h4>{esc(label)}</h4>'
                f'<p>{esc(item["value"])}</p><p class="muted">'
                f"{code(row['current_applicability'])}; "
                f"уровень: {', '.join(code(value) for value in row['student_level'])}. "
                f"{esc(row['explanation'])}</p><details><summary>Цитаты и основания</summary>"
                f"{evidence(source, item['evidence_refs'])}</details></section>"
            )
            fact_supported = all(
                row[key] == "supported"
                for key in ("text_verdict", "identity_verdict", "object_relation")
            )
            corrected = (
                row["field_verdict"] == "misclassified" and row["corrected_field"] is not None
            )
            # Display supported historical/negative/additional facts with their
            # explicit applicability; original-field coverage is a separate metric.
            show_fact = derived["usable_coverage"] or (
                fact_supported and (row["field_verdict"] == "correct" or corrected)
            )
            (established if show_fact else pending).append(block)
        topics = profile.get("topics", [])
        catalogue = esc(
            ", ".join(
                str(row.get("name", row.get("display_name", row)))
                if isinstance(row, dict)
                else str(row)
                for row in topics
            )
        )
        summary = result["summary"]
        unknown = "".join(
            f"<li>{esc(LABELS[field])}</li>"
            for field, status in source.get("field_statuses", {}).items()
            if status != "found" and field != "topic"
        )
        articles.append(
            f'<article id="{esc(aid)}"><h2>{esc(profile["name"])}</h2>'
            f'<p class="muted">{esc(aid)} · вуз в исходном каталоге: '
            f"{esc(profile['institution'])}</p>"
            f'<ul class="axes">{"".join(axes)}</ul>'
            f'<div class="notice"><b>Возможность сейчас — оценка проверяющего:</b> '
            f"{esc(summary['current_opportunity'])}</div>"
            "<h3>Сведения, прошедшие агентскую проверку</h3>"
            f"{''.join(established) or '<p>Не установлены.</p>'}"
            f"<h3>Что остаётся неизвестным</h3><p>{esc(summary['unknown'])}</p>"
            "<details><summary>Поля без находок в ограниченном поиске</summary>"
            f"<ul>{unknown}</ul></details>"
            "<details><summary>Кандидаты, которым недостаточно оснований "
            f"({len(pending)})</summary>{''.join(pending)}</details>"
            "<details><summary>Направления из исходного каталога</summary>"
            f"<p>{catalogue or 'Нет данных.'}</p>"
            "<p>Публикации и библиометрика не пересобирались.</p></details>"
            "</article>"
        )
    page = (
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Публичные сведения об исследователях</title>"
        "<style>body{font:17px/1.5 system-ui;background:#f1f4f6;color:#182a38;max-width:1080px;"
        "margin:30px auto;padding:20px}article{background:white;padding:28px;margin:28px 0;"
        "border-radius:14px}h1,h2,h3,h4{line-height:1.25}.muted{color:#5b6873;font-size:15px}"
        ".notice{background:#e8f0f8;padding:18px;border-radius:8px}"
        ".fact{border-top:1px solid #dce2e8;margin-top:18px;padding-top:5px}"
        "details{padding:12px 0}summary{cursor:pointer;color:#225d86}"
        "blockquote{white-space:pre-wrap;font-size:15px;border-left:3px solid #8badbf;padding:12px;"
        "overflow-wrap:anywhere}.quote{margin:15px 0}.axes li{margin:10px 0}"
        "a{color:#225d86}</style>"
        "<h1>Публичные сведения об исследователях</h1><p>Ограниченный эксперимент: "
        "сбор публичных источников и независимая проверка агентом. "
        "Человеческая проверка: 0. Неизвестность не означает отказ принимать студентов.</p>"
        f"<p>Карточек: {len(articles)}.</p>{''.join(articles)}</html>"
    )
    immutable(output, page.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    render(args.root, args.output)


if __name__ == "__main__":
    main()
