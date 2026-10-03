"""Strict client event contract. No arbitrary text or browser supplied server facts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

EventName = Literal[
    "visit_started",
    "search_attempt",
    "search_validation_failed",
    "results_shown",
    "weak_shown",
    "empty_shown",
    "search_error",
    "profile_opened",
    "profile_direct",
    "search_reformulated",
    "topic_followed",
    "filters_applied",
    "sort_applied",
    "work_selected",
    "work_confirmed",
    "letter_copy_success",
    "letter_copy_failed",
    "address_copy_success",
    "address_copy_failed",
]


def supported_text(value: str) -> str:
    if "\x00" in value:
        raise ValueError("unsupported text character")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("unsupported text encoding") from None
    return value


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    institution: list[str] = Field(default_factory=list, max_length=20)
    min_h_index: float | None = Field(default=None, ge=0, le=10000)

    @field_validator("institution")
    @classmethod
    def lengths(cls, values: list[str]) -> list[str]:
        if any(len(value) > 200 for value in values):
            raise ValueError("institution exceeds limit")
        for value in values:
            supported_text(value)
        return values


class EventData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    author_id: str | None = Field(default=None, max_length=100)
    position: int | None = Field(default=None, ge=1, le=1000)
    work_id: str | None = Field(default=None, max_length=100)
    work_position: int | None = Field(default=None, ge=0, le=100)
    previous_search_id: UUID | None = None
    source: Literal["submitted", "repeat", "reformulated", "topic", "direct", "results"] | None = (
        None
    )
    confidence: Literal["none", "weak", "ok"] | None = None
    error: (
        Literal[
            "validation",
            "http_422",
            "http_429",
            "http_502",
            "http_503",
            "http_504",
            "http_other",
            "timeout",
            "network",
            "receiver",
        ]
        | None
    ) = None
    filter_count: int | None = Field(default=None, ge=0, le=100)
    filters: Filters | None = None
    sort: Literal["relevance", "h_index", "citations"] | None = None
    viewport: Literal["mobile", "desktop"] | None = None
    elapsed_ms: float | None = Field(default=None, ge=0, le=86400000)
    release: str | None = Field(default=None, max_length=100)
    included: bool | None = None
    query_length: int | None = Field(default=None, ge=0, le=100000)

    @field_validator("author_id", "work_id", "release")
    @classmethod
    def strings_supported(cls, value: str | None) -> str | None:
        return supported_text(value) if value is not None else None


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    event_id: UUID
    visit_id: UUID
    search_id: UUID | None = None
    request_id: UUID | None = None
    name: EventName
    client_at: datetime
    client_seq: int = Field(ge=0, le=2147483647)
    page: Literal["home", "results", "profile"]
    data: EventData = Field(default_factory=EventData)

    @field_validator("client_at")
    @classmethod
    def timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("client_at must contain timezone")
        return value


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[Event] = Field(min_length=1, max_length=10)
