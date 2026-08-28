"""Contract smoke tests against the live OpenAlex API.

Not run in CI (`-m "not integration"`); run locally via `make test-integration`.
Verifies that the exact fields the pipeline relies on actually exist.
"""

import os
from pathlib import Path

import pytest

from sfr_etl.abstracts import reconstruct_abstract
from sfr_etl.client import OpenAlexClient

pytestmark = pytest.mark.integration

MAILTO = os.environ.get("OPENALEX_MAILTO", "")
if not MAILTO:  # allow running without exported env by reading .env via settings
    try:
        from sfr_core.settings import get_settings

        MAILTO = get_settings().openalex_mailto
    except Exception:  # pragma: no cover - env misconfiguration
        MAILTO = ""


@pytest.fixture
def client(tmp_path: Path) -> OpenAlexClient:
    assert MAILTO, "OPENALEX_MAILTO must be configured for integration tests"
    return OpenAlexClient(MAILTO, cache_dir=tmp_path / "raw", max_rps=5.0)


def test_institutions_search_contract(client: OpenAlexClient) -> None:
    body = client.get("/institutions", {"search": "Moscow Institute of Physics and Technology"})
    assert body["meta"]["count"] >= 1
    record = body["results"][0]
    assert record["id"].startswith("https://openalex.org/I")
    assert record["display_name"]
    assert "country_code" in record
    assert isinstance(record.get("display_name_alternatives"), list)


def test_authors_page_contract(client: OpenAlexClient) -> None:
    body = client.get(
        "/authors",
        {
            "filter": "last_known_institutions.id:I153845743",
            "sort": "works_count:desc",
            "per-page": 3,
            "cursor": "*",
        },
    )
    assert body["meta"]["next_cursor"]  # cursor pagination available
    record = body["results"][0]
    assert record["id"].startswith("https://openalex.org/A")
    assert record["display_name"]
    assert isinstance(record["works_count"], int)
    assert "h_index" in record["summary_stats"]
    assert "i10_index" in record["summary_stats"]
    assert isinstance(record["counts_by_year"], list)
    assert isinstance(record["topics"], list)
    assert isinstance(record["last_known_institutions"], list)


def test_work_with_abstract_contract(client: OpenAlexClient) -> None:
    body = client.get(
        "/works",
        {
            "filter": "authorships.author.id:A5028169517,has_abstract:true",
            "per-page": 1,
            "select": (
                "id,display_name,publication_year,cited_by_count,"
                "language,topics,abstract_inverted_index"
            ),
        },
    )
    record = body["results"][0]
    assert record["id"].startswith("https://openalex.org/W")
    assert record["display_name"]
    assert isinstance(record["publication_year"], int)
    assert isinstance(record["cited_by_count"], int)
    abstract = reconstruct_abstract(record["abstract_inverted_index"])
    assert abstract and len(abstract) > 50
