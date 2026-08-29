"""One end-to-end pass with the real model and the real index.

Excluded from ``make test`` (loads FRIDA, ~2 GB of weights); run with ``make test-slow``.
"""

import pytest
from fastapi.testclient import TestClient

from sfr_api.main import create_app
from sfr_api.settings import ApiSettings

pytestmark = pytest.mark.slow


def test_real_index_answers_a_real_query() -> None:
    settings = ApiSettings()
    if not (settings.resolved_index_dir() / "meta.json").exists():
        pytest.skip(f"нет индекса {settings.resolved_index_dir()} — сначала `make index-sfr2`")
    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health").json()
        assert health["profiles_count"] > 100

        body = client.post(
            "/api/match",
            json={"query": "нейросети для медицинских изображений", "k": 5},
        ).json()
        assert len(body["results"]) == 5
        assert body["index_version"] == health["index_version"]
        assert body["results"][0]["score"] > body["results"][-1]["score"]
        assert body["results"][0]["profile_text"]

        card = client.get(f"/api/supervisors/{body['results'][0]['author_id']}").json()
        assert card["name"] == body["results"][0]["name"]
