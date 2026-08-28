"""Pydantic export schemas: one JSONL line per supervisor profile (input for SFR-1 embeddings)."""

from pydantic import BaseModel


class WorkExport(BaseModel):
    openalex_id: str
    title: str
    publication_year: int | None = None
    cited_by_count: int = 0
    has_abstract: bool = False


class ProfileExport(BaseModel):
    id: str  # author openalex_id
    name: str
    institution: str | None = None
    h_index: int | None = None
    topics: list[str] = []
    profile_text: str
    works: list[WorkExport] = []
