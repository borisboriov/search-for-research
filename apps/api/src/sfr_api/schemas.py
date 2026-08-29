"""Request/response contract of the API.

Product decision (MVP plan v1.3): supervisor cards are open and free — the API
returns the whole card without authentication. Monetisation lands on services
built around the data, not on the data itself.
"""

from typing import Any

from pydantic import BaseModel, Field


class SupervisorCard(BaseModel):
    author_id: str
    name: str
    institution: str | None = None
    h_index: int | None = None
    works_count: int | None = None
    topics: list[str] = []
    profile_text: str

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "SupervisorCard":
        return cls(
            author_id=str(doc["id"]),
            name=str(doc["name"]),
            institution=doc.get("institution"),
            h_index=doc.get("h_index"),
            works_count=doc.get("works_count"),
            topics=list(doc.get("topics") or []),
            profile_text=str(doc.get("display_text") or doc["profile_text"]),
        )


class MatchResult(SupervisorCard):
    score: float = Field(description="Cosine similarity with the query, 0..1")
    rank: int


class MatchRequest(BaseModel):
    query: str
    k: int | None = None


class MatchResponse(BaseModel):
    results: list[MatchResult]
    below_threshold: bool = Field(
        description="Top-1 score is under the cut-off: show 'no confident matches' — "
        "a warning above the results, not a refusal to show them"
    )
    index_version: str
    took_ms: float


class HealthResponse(BaseModel):
    status: str
    model: str
    index_version: str
    profiles_count: int
    score_threshold: float
    search_backend: str
    compose: str
    built_at: str
