"""Pydantic export schemas: one JSONL line per supervisor profile (input for SFR-1 embeddings)."""

from pydantic import BaseModel


class WorkExport(BaseModel):
    openalex_id: str
    title: str
    publication_year: int | None = None
    cited_by_count: int = 0
    has_abstract: bool = False


class TopWorkCard(BaseModel):
    """One publication on the public card (SFR-3): title first — titles carry the signal."""

    title: str
    year: int | None = None


class CardExport(BaseModel):
    """Card enrichment for the API (SFR-3, `sfr export cards`): what the search
    index does not carry but the supervisor page shows.

    ``position`` and ``email`` are declared but always ``None`` for now: OpenAlex
    does not provide them and nothing new is parsed (SPEC_SFR3 §4). They exist so
    that the contract does not change when a source appears.
    """

    id: str  # author openalex_id
    cited_by_count: int | None = None
    position: str | None = None
    email: str | None = None
    top_works: list[TopWorkCard] = []


class ProfileExport(BaseModel):
    id: str  # author openalex_id
    name: str
    institution: str | None = None
    h_index: int | None = None
    # Total works known to OpenAlex, not the number of ingested ``works`` below.
    works_count: int | None = None
    topics: list[str] = []
    profile_text: str
    works: list[WorkExport] = []
