"""Contract of the endpoints, driven by the fake backend (SPEC_SFR2 §2, SFR-3 §4)."""

import json
from pathlib import Path

import pytest
from conftest import DOCS, FakeBackend, write_index
from fastapi.testclient import TestClient

from sfr_api.main import create_app
from sfr_api.service import MatchService
from sfr_api.settings import ApiSettings


def client(backend: FakeBackend, **overrides: object) -> TestClient:
    settings = ApiSettings(warmup=False, **overrides)  # type: ignore[arg-type]
    return TestClient(create_app(settings, MatchService(backend, settings)))


def test_health_names_the_model_and_the_index_it_serves(backend: FakeBackend) -> None:
    body = client(backend).get("/api/health").json()
    assert body["status"] == "ok"
    assert body["model"] == "ai-forever/FRIDA"
    assert body["profiles_count"] == 3
    assert body["index_version"].startswith("frida_clean-3p-")
    assert body["score_threshold"] == pytest.approx(0.27)
    assert body["search_backend"] in {"faiss", "numpy"}


def test_match_returns_open_cards_with_every_field(backend: FakeBackend) -> None:
    body = client(backend).post("/api/match", json={"query": "оптимизация маршрутов"}).json()
    top = body["results"][0]
    assert top["author_id"] == "A2"
    assert top["name"] == "Anton Agafonov"
    assert top["institution"] == "МГУ"
    assert top["h_index"] == 12
    assert top["works_count"] == 90
    assert top["topics"] == ["Transportation Planning and Optimization"]
    assert top["profile_text"].startswith("Anton Agafonov")
    assert 0.0 <= top["score"] <= 1.0
    assert top["rank"] == 1
    assert body["index_version"] == backend.meta.version


def test_results_are_ranked_by_descending_score(backend: FakeBackend) -> None:
    body = client(backend).post("/api/match", json={"query": "нейросети изображения"}).json()
    scores = [result["score"] for result in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert [result["rank"] for result in body["results"]] == [1, 2, 3]


def test_below_threshold_is_true_when_the_top_score_is_under_the_cutoff() -> None:
    body = client(FakeBackend(top_score=0.21)).post("/api/match", json={"query": "право"}).json()
    assert body["below_threshold"] is True
    assert body["results"], "порог — предупреждение, а не отказ: выдача всё равно возвращается"


def test_below_threshold_is_false_above_the_cutoff() -> None:
    body = client(FakeBackend(top_score=0.34)).post("/api/match", json={"query": "нейтрино"}).json()
    assert body["below_threshold"] is False


def test_threshold_comes_from_settings() -> None:
    payload = {"query": "нейтрино"}
    high = client(FakeBackend(top_score=0.34), score_threshold=0.9).post("/api/match", json=payload)
    assert high.json()["below_threshold"] is True


def test_k_defaults_to_ten_and_can_be_narrowed(backend: FakeBackend) -> None:
    api = client(backend)
    assert len(api.post("/api/match", json={"query": "нейтрино"}).json()["results"]) == 3
    assert len(api.post("/api/match", json={"query": "нейтрино", "k": 1}).json()["results"]) == 1


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        # пустая строка режется уже схемой (min_length=3) — текст общий, не сервисный
        ({"query": ""}, "не прошёл проверку"),
        ({"query": "  ab  "}, "слишком короткий"),
        ({"query": "я" * 501}, "слишком длинный"),
        # длиннее max_length схемы (2000) — страховка от мегабайтных тел
        ({"query": "я" * 2001}, "не прошёл проверку"),
        ({"query": "нейтрино", "k": 0}, "k должно быть"),
        ({"query": "нейтрино", "k": 999}, "k должно быть"),
    ],
)
def test_invalid_requests_get_a_human_readable_422(
    backend: FakeBackend, payload: dict[str, object], fragment: str
) -> None:
    response = client(backend).post("/api/match", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str) and fragment in detail


def test_malformed_body_also_gets_a_sentence_not_a_pydantic_dump(backend: FakeBackend) -> None:
    response = client(backend).post("/api/match", json={"k": 5})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_match_returns_503_when_inference_queue_is_full(backend: FakeBackend) -> None:
    """Сверх concurrency+queue запрос не встаёт в хвост, а сразу получает 503."""
    api = client(backend, match_concurrency=1, match_queue_limit=0)
    api.app.state.match_inflight = 1  # как будто один запрос уже кодируется
    response = api.post("/api/match", json={"query": "нейтрино"})
    assert response.status_code == 503
    assert "перегружен" in response.json()["detail"]
    api.app.state.match_inflight = 0
    assert api.post("/api/match", json={"query": "нейтрино"}).status_code == 200


def test_match_inflight_counter_returns_to_zero_after_requests(backend: FakeBackend) -> None:
    api = client(backend)
    api.post("/api/match", json={"query": "нейтрино"})
    api.post("/api/match", json={"query": "  ab  "})  # и после 422 тоже
    assert api.app.state.match_inflight == 0


def test_supervisor_card_is_available_by_id(backend: FakeBackend) -> None:
    body = client(backend).get("/api/supervisors/A1").json()
    assert body["name"] == "Л. В. Инжечик"
    assert body["works_count"] == 412
    assert "score" not in body


def test_unknown_supervisor_is_a_404_with_the_id_in_it(backend: FakeBackend) -> None:
    response = client(backend).get("/api/supervisors/A999")
    assert response.status_code == 404
    assert "A999" in response.json()["detail"]


def test_cors_allows_the_future_front_on_localhost(backend: FakeBackend) -> None:
    response = client(backend).post(
        "/api/match",
        json={"query": "нейтрино"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_a_missing_index_fails_at_startup_not_on_the_first_query(tmp_path: Path) -> None:
    settings = ApiSettings(index_dir=tmp_path / "nothing", warmup=False)
    with (
        pytest.raises(FileNotFoundError, match="make index-sfr2"),
        TestClient(create_app(settings)),
    ):
        pass


def test_service_opens_the_index_directory_named_by_settings(tmp_path: Path) -> None:
    settings = ApiSettings(index_dir=write_index(tmp_path / "frida_clean"), warmup=False)
    service = MatchService.from_settings(settings)
    assert service.health().profiles_count == len(DOCS)
    assert service.card("A1") is not None


def test_from_settings_warms_the_backend_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = FakeBackend()
    monkeypatch.setattr("sfr_api.service.load_backend", lambda *args, **kwargs: backend)
    settings = ApiSettings(index_dir=write_index(tmp_path / "frida_clean"), warmup=True)
    MatchService.from_settings(settings)
    assert backend.warmups == 1


# --- SFR-3 §4: card enrichment and the catalogue listing -----------------------------

EXTRAS = {
    "A1": {
        "id": "A1",
        "cited_by_count": 4210,
        "position": None,
        "email": None,
        "top_works": [{"title": "GERDA: final results", "year": 2020}],
    }
}


def enriched_client(backend: FakeBackend, tmp_path: Path) -> TestClient:
    cards = tmp_path / "cards.jsonl"
    cards.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in EXTRAS.values()),
        encoding="utf-8",
    )
    settings = ApiSettings(warmup=False, cards_path=cards)
    return TestClient(create_app(settings, MatchService(backend, settings)))


def test_card_is_enriched_from_the_cards_file(backend: FakeBackend, tmp_path: Path) -> None:
    body = enriched_client(backend, tmp_path).get("/api/supervisors/A1").json()
    assert body["cited_by_count"] == 4210
    assert body["top_works"] == [{"title": "GERDA: final results", "year": 2020}]
    assert body["position"] is None and body["email"] is None


def test_match_results_carry_the_same_enrichment(backend: FakeBackend, tmp_path: Path) -> None:
    body = enriched_client(backend, tmp_path).post("/api/match", json={"query": "нейтрино"}).json()
    by_id = {r["author_id"]: r for r in body["results"]}
    assert by_id["A1"]["cited_by_count"] == 4210
    assert by_id["A2"]["cited_by_count"] is None  # not in the enrichment file
    assert by_id["A2"]["top_works"] == []


def test_missing_cards_file_degrades_to_empty_fields(backend: FakeBackend) -> None:
    """The enrichment is optional by design: no file — no crash, empty fields."""
    body = client(backend, cards_path=Path("nowhere/cards.jsonl")).get("/api/supervisors/A1").json()
    assert body["cited_by_count"] is None
    assert body["top_works"] == []


def test_serendipity_is_declared_but_never_set_by_the_api(backend: FakeBackend) -> None:
    body = client(backend).post("/api/match", json={"query": "нейтрино"}).json()
    assert all(result["serendipity"] is False for result in body["results"])


def test_supervisors_listing_returns_every_profile(backend: FakeBackend) -> None:
    body = client(backend).get("/api/supervisors").json()
    assert body["total"] == 3
    assert [item["author_id"] for item in body["items"]] == ["A1", "A2", "A3"]
    assert body["items"][0]["name"] == "Л. В. Инжечик"
    assert body["items"][0]["institution"] == "МФТИ"
    assert body["next_cursor"] is None


def test_supervisors_listing_paginates_by_cursor(backend: FakeBackend) -> None:
    api = client(backend)
    first = api.get("/api/supervisors", params={"limit": 2}).json()
    assert [item["author_id"] for item in first["items"]] == ["A1", "A2"]
    assert first["next_cursor"] == "A2"
    second = api.get("/api/supervisors", params={"limit": 2, "cursor": "A2"}).json()
    assert [item["author_id"] for item in second["items"]] == ["A3"]
    assert second["next_cursor"] is None


def test_get_422_does_not_mention_json_body(backend: FakeBackend) -> None:
    """На GET /supervisors?limit=abc подсказка про query-параметры, не про JSON."""
    response = client(backend).get("/api/supervisors", params={"limit": "abc"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "query-параметр" in detail
    assert "JSON" not in detail


def test_supervisors_listing_rejects_bad_limit_and_cursor(backend: FakeBackend) -> None:
    api = client(backend)
    assert api.get("/api/supervisors", params={"limit": 0}).status_code == 422
    assert api.get("/api/supervisors", params={"limit": 9999}).status_code == 422
    response = api.get("/api/supervisors", params={"cursor": "A999"})
    assert response.status_code == 422
    assert "A999" in response.json()["detail"]
