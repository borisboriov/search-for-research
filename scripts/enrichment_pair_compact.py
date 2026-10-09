"""Отдельное компактное представление слепого пакета без изменения исходников.

Сохраняет исходный HTML дословно внутри добавленных раскрывающихся блоков.
Не извлекает фактов и не меняет решения, вопросы, разметку или JavaScript.
"""

import argparse
import hashlib
import html
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from enrichment_experiment import private_root, sha
from enrichment_verification import identifier, immutable_bytes

VERSION = "compact-v3"
NOTICE = (
    '<aside class="compact-notice"><p><strong>Как читать вопросы:</strong> '
    "вопросы агентов могут быть сформулированы как обращение к учёному. "
    "Вам нужно оценить корректность ответов по сохранённым источникам, "
    "а не отвечать от имени учёного. Исходные вопросы и ответы сохранены. "
    "Длинные и повторяющиеся цитаты раскрываются отдельно и приведены полностью.</p></aside>"
)


class QuoteSpans(HTMLParser):
    """Фиксирует смещения в исходной строке, не пересериализуя HTML."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        # HTMLParser advances line numbers only at LF. str.splitlines() also
        # splits U+2028/U+2029, vertical tab and bare CR found in source pages.
        # Those would corrupt offsets while the original HTML remains valid.
        self.lines = [0] + [index + 1 for index, char in enumerate(source) if char == "\n"]
        self.stack: list[int] = []
        self.quotes: list[tuple[int, int]] = []
        self.article: int | None = None
        self.scripts: list[str] = []
        self.script_start: int | None = None
        self.details_stack: list[dict[str, Any]] = []
        self.summary_start: int | None = None
        self.pre_start: int | None = None
        self.invalid_pres: list[tuple[int, str]] = []

    def position(self) -> int:
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "details":
            self.details_stack.append({"start": self.position(), "invalid": False})
        if tag == "summary":
            self.summary_start = self.position() + len(self.get_starttag_text() or "")
        if tag == "pre":
            self.pre_start = self.position() + len(self.get_starttag_text() or "")
        if tag == "blockquote":
            if self.stack:
                raise ValueError("Вложенные blockquote не поддерживаются")
            self.stack.append(self.position())
        if tag == "article" and self.article is None:
            self.article = self.position()
        if tag == "script":
            if self.script_start is not None:
                raise ValueError("Вложенный script")
            self.script_start = self.position()

    def handle_endtag(self, tag: str) -> None:
        end = self.source.index(">", self.position()) + 1
        if tag == "summary" and self.summary_start is not None:
            title = html.unescape(self.source[self.summary_start : self.position()]).strip()
            if self.details_stack and title == "Исходный ответ с ошибками":
                self.details_stack[-1]["invalid"] = True
            self.summary_start = None
        if tag == "pre" and self.pre_start is not None:
            if self.details_stack and self.details_stack[-1]["invalid"]:
                self.invalid_pres.append(
                    (self.details_stack[-1]["start"], self.source[self.pre_start : self.position()])
                )
            self.pre_start = None
        if tag == "details":
            if not self.details_stack:
                raise ValueError("Закрывающий details без начала")
            self.details_stack.pop()
        if tag == "blockquote":
            if not self.stack:
                raise ValueError("Закрывающий blockquote без начала")
            self.quotes.append((self.stack.pop(), end))
        if tag == "script" and self.script_start is not None:
            self.scripts.append(self.source[self.script_start : end])
            self.script_start = None

    def finish(self) -> None:
        self.feed(self.source)
        self.close()
        if self.stack or self.script_start is not None or self.details_stack:
            raise ValueError("Незавершённая цитата или script")


KEYS = {
    "items": "Оценки утверждений",
    "item_id": "Идентификатор утверждения",
    "text_verdict": "Подтверждение текстом",
    "identity_verdict": "Связь с человеком",
    "field_verdict": "Соответствие смыслу поля",
    "corrected_field": "Предлагаемое поле",
    "fact_kind": "Вид факта",
    "object_type": "Объект утверждения",
    "object_relation": "Связь объекта с человеком",
    "student_level": "Уровень студента",
    "information_date": "Дата сведений",
    "date_basis": "Основание даты",
    "current_applicability": "Текущая применимость",
    "evidence_refs": "Ссылки на доказательства",
    "explanation": "Объяснение",
    "question": "Исходный вопрос агента",
    "profile_assessments": "Оценки человека и аффилиации",
    "identity": "Личность",
    "current_affiliation": "Нынешняя аффилиация",
    "activity": "Профессиональная активность",
    "verdict": "Решение",
    "status": "Статус",
    "summary": "Краткий вывод",
    "known": "Что известно",
    "unknown": "Что неизвестно",
    "current_opportunity": "Актуальность возможности",
    "validation": "Автоматическая проверка",
    "errors": "Ошибки проверки",
    "succeeded": "Проверка пройдена",
}
CODES = {
    "supported": "Подтверждено",
    "insufficient": "Недостаточно оснований",
    "conflicting": "Источники противоречат",
    "refuted": "Опровергнуто",
    "confirmed_by_source": "Подтверждено текстом источника",
    "insufficient_evidence": "Недостаточно оснований",
    "sources_conflict": "Источники противоречат",
    "correct": "Соответствует полю",
    "misclassified": "Неверно отнесено к полю",
    "reclassified": "Классификация исправлена",
    "scientist": "Человек",
    "laboratory": "Лаборатория",
    "organization": "Организация",
    "offer": "Предложение",
    "undergraduate": "Бакалавриат",
    "masters": "Магистратура",
    "phd": "Аспирантура / PhD",
    "postdoc": "Постдок",
    "unknown": "Не установлено",
    "current": "Текущая применимость",
    "historical": "Исторические сведения",
    "undated": "Дата неизвестна",
    "expired": "Срок истёк",
    "closed": "Предложение закрыто",
    "explicit_negative": "Явное отрицание",
    "active": "Есть профессиональная активность",
    "deceased": "Есть подтверждение смерти",
    "ceased": "Есть подтверждение прекращения работы",
    "content": "Дата в содержании",
    "source_metadata": "Дата в метаданных",
    "url_only": "Дата только в адресе страницы",
    "unknown_date": "Дата не установлена",
    "literal": "Буквальный факт",
    "appointment_duration": "Длительность договора",
    "nationality": "Гражданство",
    "person_status": "Статус человека",
    "weekly_effort": "Еженедельная нагрузка",
    "effort": "Рабочая нагрузка",
    "institutional_external": "Допуск студента из другого вуза",
    "intake": "Опубликованный набор",
    "willingness": "Готовность",
    "institutional_membership": "Принадлежность студента к вузу",
    "supervision_history": "История руководства",
    "recruitment": "Объявление о наборе",
    "personal_willingness": "Личная готовность",
    "contact": "Контакт",
    "student_opportunity": "Возможность для студента",
    "institutional_scope": "Область подразделения",
}
ENUM_KEYS = {
    "text_verdict",
    "identity_verdict",
    "field_verdict",
    "corrected_field",
    "fact_kind",
    "object_type",
    "object_relation",
    "student_level",
    "date_basis",
    "current_applicability",
    "verdict",
    "status",
}

ENUM_VALUES = {
    "text_verdict": {"supported", "refuted", "insufficient", "conflicting"},
    "identity_verdict": {"supported", "refuted", "insufficient", "conflicting"},
    "verdict": {"supported", "refuted", "insufficient", "conflicting"},
    "field_verdict": {"correct", "misclassified", "insufficient"},
    "fact_kind": {
        "literal",
        "effort",
        "appointment_duration",
        "institutional_external",
        "nationality",
        "supervision_history",
        "intake",
        "willingness",
        "person_status",
    },
    "object_type": {"scientist", "laboratory", "organization", "offer"},
    "object_relation": {"supported", "insufficient", "conflicting"},
    "student_level": {"undergraduate", "masters", "phd", "postdoc", "unknown"},
    "date_basis": {"content", "source_metadata", "url_only", "conflicting", "unknown"},
    "current_applicability": {
        "current",
        "historical",
        "expired",
        "undated",
        "unknown",
        "explicit_negative",
    },
    "status": {"active", "deceased", "ceased", "unknown"},
}

ITEM_KEYS = (
    "item_id",
    "text_verdict",
    "identity_verdict",
    "field_verdict",
    "corrected_field",
    "fact_kind",
    "object_type",
    "object_relation",
    "student_level",
    "information_date",
    "date_basis",
    "current_applicability",
    "evidence_refs",
    "explanation",
    "question",
)
AXIS_KEYS = ("verdict", "evidence_refs", "information_date", "date_basis", "explanation")


def readable_invalid(
    value: dict[str, Any],
    profile: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> str:
    """Показывает оригинальные значения; не ремонтирует их и не присваивает вердикты."""
    from enrichment_verification import LABELS

    codes = CODES | LABELS
    pool = profile.get("evidence_pool", {}) if profile is not None else None

    def display(key: str, item: Any) -> str:
        if item is None:
            return "В исходном ответе указано null"
        if key == "student_level" and item == []:
            return "Не указан (ошибка ответа)"
        if key == "evidence_refs" and item == []:
            return "Ссылки не приведены"
        if isinstance(item, list):
            return "<ul>" + "".join("<li>" + display(key, x) + "</li>" for x in item) + "</ul>"
        if isinstance(item, dict):
            return table(item)
        if key == "evidence_refs" and pool is not None and item not in pool:
            return "Неизвестная ссылка; отсутствует в общем пакете: " + html.escape(str(item))
        if key in ENUM_KEYS:
            allowed = (
                set(LABELS) | {"appointment_duration", "nationality", "person_status"}
                if key == "corrected_field"
                else ENUM_VALUES[key]
            )
            if str(item) not in allowed:
                return "Неизвестный код: " + html.escape(str(item))
            if key == "date_basis" and item == "conflicting":
                return "Даты противоречат друг другу"
            return html.escape(codes.get(str(item), "Неизвестный код: " + str(item)))
        if isinstance(item, bool):
            return "Да" if item else "Нет"
        return html.escape(str(item))

    def table(row: dict[str, Any], required: tuple[str, ...] = ()) -> str:
        keys = list(dict.fromkeys((*required, *row)))
        rendered = []
        for key in keys:
            title = KEYS.get(key, "Дополнительный ключ («" + key + "»)")
            content = display(key, row[key]) if key in row else "Отсутствует (ошибка ответа)"
            rendered.append("<tr><th>" + html.escape(title) + "</th><td>" + content + "</td></tr>")
        return "<table>" + "".join(rendered) + "</table>"

    parts = [
        '<section class="compact-invalid"><h4>Оригинальный ответ: НЕ ПРИНЯТ</h4>',
        "<p>Ответ не прошёл автоматическую проверку. Ниже читаемое представление "
        "его исходных значений, без исправлений и без принятия утверждений. "
        "Точный исходный JSON остаётся под раскрытием.</p>",
    ]
    parts.append(
        "<h5>Ошибки проверки</h5>"
        + display("validation", validation or value.get("validation", {}))
    )
    parts.append(
        "<h5>Краткий вывод</h5>"
        + (
            table(value["summary"], ("known", "unknown", "identity", "current_opportunity"))
            if isinstance(value.get("summary"), dict)
            else "Отсутствует или неверный тип (ошибка ответа)"
        )
    )
    parts.append("<h5>Личность, аффилиация и активность</h5>")
    axes = value.get("profile_assessments", {})
    for axis in ("identity", "current_affiliation", "activity"):
        parts.append("<h6>" + KEYS[axis] + "</h6>")
        row = axes.get(axis) if isinstance(axes, dict) else None
        parts.append(
            table(row, AXIS_KEYS + (("status",) if axis == "activity" else ()))
            if isinstance(row, dict)
            else "Отсутствует (ошибка ответа)"
        )
    parts.append("<h5>Оценки исходных утверждений</h5>")
    rows = value.get("items")
    if not isinstance(rows, list):
        parts.append("Список оценок отсутствует или имеет неверный тип (ошибка ответа)")
        rows = []
    if not rows:
        parts.append("<p>Оценки утверждений не приведены.</p>")
    for row in rows:
        parts.append(
            table(row, ITEM_KEYS)
            if isinstance(row, dict)
            else "Некорректная исходная оценка: " + html.escape(str(row))
        )
    if profile is not None:
        present = {
            row["item_id"]
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("item_id"), str)
        }
        missing = [row["item_id"] for row in profile["items"] if row["item_id"] not in present]
        if missing:
            parts.append(
                "<p><strong>Пропущены оценки атомов:</strong> "
                + html.escape(", ".join(missing))
                + " (ошибка ответа).</p>"
            )
    for key in value:
        if key in {"items", "profile_assessments", "summary", "validation"}:
            continue
        parts.append(table({key: value[key]}))
    parts.append("</section>")
    return "".join(parts)


def transform(
    source: str, *, threshold: int = 600, manifest: dict[str, Any] | None = None
) -> tuple[str, dict[str, Any]]:
    """Не сокращает исходные цитаты: меняет только их начальную видимость."""
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1:
        raise ValueError("Нужен положительный предел длины")
    parser = QuoteSpans(source)
    parser.finish()
    if parser.article is None:
        raise ValueError("В исходном пакете нет карточек article")
    insertions: list[tuple[int, str]] = [(parser.article, NOTICE)]
    expected = []
    if manifest is not None:
        for profile in manifest.get("profiles", []):
            for response in profile["responses"].values():
                if response.get("validation", {}).get("succeeded") is False:
                    expected.append((profile, response))
        if len(expected) != len(parser.invalid_pres):
            raise ValueError("Количество ошибочных ответов отличается от исходного manifest")
    for index, (offset, raw) in enumerate(parser.invalid_pres):
        value = json.loads(html.unescape(raw))
        if not isinstance(value, dict):
            raise ValueError("Исходный ошибочный ответ не объект")
        profile = None
        if manifest is not None:
            profile, original_response = expected[index]
            comparable = original_response
            if "validation" not in value:
                comparable = {
                    key: item for key, item in original_response.items() if key != "validation"
                }
            if value != comparable:
                raise ValueError("Ошибочный ответ не совпадает с исходным manifest")
        validation = expected[index][1].get("validation") if manifest is not None else None
        insertions.append((offset, readable_invalid(value, profile, validation)))
    seen: set[str] = set()
    wrapped = 0
    repeated = 0
    for start, end in parser.quotes:
        raw = source[start:end]
        text = html.unescape(raw[raw.index(">") + 1 : raw.rindex("</")])
        digest = hashlib.sha256(text.encode()).hexdigest()
        duplicate = digest in seen
        seen.add(digest)
        if len(text) <= threshold and not duplicate:
            continue
        repeated += int(duplicate)
        wrapped += 1
        prefix = (
            '<details class="compact-source"><summary>Полная дословная цитата '
            f"({len(text)} символов" + ("; повтор источника" if duplicate else "") + ")</summary>"
        )
        insertions.extend(((start, prefix), (end, "</details>")))
    result = source
    for offset, value in sorted(insertions, key=lambda item: item[0], reverse=True):
        result = result[:offset] + value + result[offset:]
    check = QuoteSpans(result)
    check.finish()
    if check.scripts != parser.scripts:
        raise ValueError("JavaScript изменился")
    if [result[a:b] for a, b in check.quotes] != [source[a:b] for a, b in parser.quotes]:
        raise ValueError("Исходная цитата изменилась")
    return result, {
        "quote_count": len(parser.quotes),
        "collapsed_quote_count": wrapped,
        "repeated_collapsed_quote_count": repeated,
        "threshold_characters": threshold,
        "scripts_unchanged": True,
        "invalid_responses_rendered": len(parser.invalid_pres),
    }


def render(root: Path, packet_id: str, *, threshold: int = 600) -> Path:
    root = private_root(root)
    identifier(packet_id)
    original = root / "paired-human" / "packets" / packet_id
    source_path, manifest_path = original / "cards.html", original / "manifest.json"
    payload = source_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    if manifest.get("schema") != "paired_human_packet_v1" or manifest.get("packet_id") != packet_id:
        raise ValueError("Другой исходный пакет")
    compact, stats = transform(payload.decode("utf-8"), threshold=threshold, manifest=manifest)
    destination = root / "paired-human" / VERSION / packet_id
    receipt = {
        "schema": "paired_human_representation_v1",
        "representation_version": VERSION,
        "script_sha256": sha(Path(__file__)),
        "packet_id": packet_id,
        "source_html_sha256": digest,
        "manifest_sha256": manifest_digest,
        "compact_html_sha256": hashlib.sha256(compact.encode()).hexdigest(),
        "source_html_path": str(source_path),
        "manifest_path": str(manifest_path),
        "human_review_records_changed": False,
        "source_records_changed": False,
        **stats,
    }
    # Check originals again before publishing, including a concurrently modified packet.
    if sha(source_path) != digest or sha(manifest_path) != manifest_digest:
        raise ValueError("Исходный пакет изменился во время преобразования")
    immutable_bytes(destination / "cards.html", compact.encode())
    immutable_bytes(
        destination / "receipt.json",
        (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode(),
    )
    return destination / "cards.html"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--packet-id", required=True)
    parser.add_argument("--threshold", type=int, default=600)
    args = parser.parse_args()
    print(render(args.root, args.packet_id, threshold=args.threshold))


if __name__ == "__main__":
    main()
