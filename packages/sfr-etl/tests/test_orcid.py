"""ORCID на чужое имя в дедупликации (#118): клиент с кэшем и правило."""

import json
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import Engine, delete
from test_dedup import SETTINGS, engine, record  # noqa: F401 — фикстура engine
from test_ingest import INSTITUTION_RECORD

from sfr_core.db import session_scope
from sfr_core.models import Author, AuthorTopic
from sfr_etl.dedup import find_splits
from sfr_etl.ingest import upsert_author, upsert_institution
from sfr_etl.orcid import (
    OrcidClient,
    OrcidName,
    foreign_orcid_note,
    orcid_on_another_name,
    parse_person,
)


def _person(given: str, family: str) -> dict[str, Any]:
    return {"name": {"given-names": {"value": given}, "family-name": {"value": family}}}


def _author(name: str, alternatives: list[str] | None = None) -> Author:
    return Author(
        openalex_id="A0", display_name=name, raw={"display_name_alternatives": alternatives or []}
    )


def test_parse_person_reads_the_name_and_hidden_name_is_none() -> None:
    assert parse_person(_person("Nikita", "Usachev")) == OrcidName("Nikita", "Usachev")
    assert parse_person({"name": None}) is None


def test_orcid_on_another_name_catches_surname_and_first_name_conflicts() -> None:
    usachev_b = _author(
        "N. A. Usachev", ["Николай Александрович Усачев", "Nikolai Alexandrovich Usachev"]
    )
    assert orcid_on_another_name(OrcidName("Nikita", "Usachev"), usachev_b)
    assert orcid_on_another_name(OrcidName("Anna", "Kozhina"), _author("A. Kraeva"))
    # Своё имя, транслитерация и одни инициалы у профиля — не чужой ORCID.
    assert not orcid_on_another_name(OrcidName("Nikolay", "Usachev"), usachev_b)
    assert not orcid_on_another_name(OrcidName("Valery", "Lukinskiy"), _author("Valery Lukinskiy"))
    assert not orcid_on_another_name(OrcidName("Nikita", "Usachev"), _author("N. Usachev"))


def test_client_caches_on_disk_one_request_per_orcid(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=_person("Nikita", "Usachev"))

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = OrcidClient(cache_dir=tmp_path, http=http)
    assert client.name("https://orcid.org/0000-0001-6051-1089") == OrcidName("Nikita", "Usachev")
    again = OrcidClient(cache_dir=tmp_path, http=http)
    assert again.name("0000-0001-6051-1089") == OrcidName("Nikita", "Usachev")
    assert calls == ["https://pub.orcid.org/v3.0/0000-0001-6051-1089/person"]
    assert (client.n_requests, again.n_requests, again.n_cache_hits) == (1, 0, 1)
    envelope = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert envelope["status"] == 200


def test_temporary_error_is_not_cached(tmp_path: Path) -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    client = OrcidClient(cache_dir=tmp_path, http=http)
    assert client.name("0000-0001-6051-1089") is None
    assert list(tmp_path.glob("*.json")) == []


def test_foreign_orcid_pair_goes_to_human_with_a_note_and_is_not_merged(
    engine: Engine,  # noqa: F811
) -> None:
    """Усачёв-подобная пара: пометка «записан на другое имя», склейки нет; без
    проверки — прежняя причина «разные ORCID»; Лукинские со своими ORCID — тоже."""
    with session_scope(engine) as session:
        inst = upsert_institution(session, INSTITUTION_RECORD)
        a = upsert_author(
            session,
            record("A1", "Nikolay A. Usachev", "0009-0008-0926-2134", 19),
            inst.id,
            SETTINGS,
        )
        b = upsert_author(
            session, record("A2", "N. A. Usachev", "0000-0001-6051-1089", 15), inst.id, SETTINGS
        )
        b.raw = {**(b.raw or {}), "display_name_alternatives": ["Николай Александрович Усачев"]}
        for author in (a, b):
            session.execute(delete(AuthorTopic).where(AuthorTopic.author_id == author.id))
            for score, name in enumerate(["Nuclear", "Reactors", "Neutrons"], start=1):
                session.add(AuthorTopic(author_id=author.id, topic_name=name, score=float(score)))
    names = {
        "0009-0008-0926-2134": OrcidName("Nikolay", "Usachev"),
        "0000-0001-6051-1089": OrcidName("Nikita", "Usachev"),
    }

    class FakeClient(OrcidClient):
        def name(self, orcid: str) -> OrcidName | None:
            return names.get(orcid)

    with session_scope(engine) as session:
        plain = find_splits(session)
        assert [g.signal for g in plain.review] == ["abbrev+institution+topics, но разные ORCID"]
        checked = find_splits(session, foreign_orcid=foreign_orcid_note(FakeClient(Path("."))))
        assert checked.merges == []
        assert len(checked.review) == 1
        signal = checked.review[0].signal
        assert "разные ORCID — ORCID 0000-0001-6051-1089 записан на другое имя" in signal
        assert "«Nikita Usachev» при «N. A. Usachev»" in signal
