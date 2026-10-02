"""Versioned journal records validated before DB replay to isolate corrupt files."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sfr_api.analytics.contracts import Event


class PrivateContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_ip: str | None = Field(default=None, max_length=64)
    url: str | None = Field(default=None, max_length=2048)
    referer: str | None = Field(default=None, max_length=2048)
    diagnostic_headers: dict[str, str]

    @field_validator("diagnostic_headers")
    @classmethod
    def allow_headers(cls, value: dict[str, str]) -> dict[str, str]:
        if set(value) - {"user-agent", "accept-language"}:
            raise ValueError("unapproved diagnostic header")
        if any(len(header) > 512 for header in value.values()):
            raise ValueError("diagnostic header exceeds limit")
        return value


class SearchContext(PrivateContext):
    search_id: UUID
    raw_query: str = Field(max_length=2000)
    normalized_query: str = Field(max_length=2000)


class EventContextRecord(PrivateContext):
    event_id: UUID
    ingest_request_id: UUID | None = None


class SearchFactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search_id: UUID
    request_id: UUID
    visit_id: UUID | None = None
    received_at: datetime
    completed_at: datetime
    status: int = Field(ge=100, le=599)
    outcome: Literal["success", "error"]
    payload: dict[str, Any]

    @field_validator("received_at", "completed_at")
    @classmethod
    def server_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("server timestamp needs timezone")
        return value

    @field_validator("payload")
    @classmethod
    def facts_only(cls, value: dict[str, Any]) -> dict[str, Any]:
        if set(value) - {
            "schema_version",
            "app_version",
            "model",
            "index_version",
            "cache_hit",
            "wall_ms",
            "k",
            "thresholds",
            "error",
            "confidence",
            "took_ms",
            "results",
            "legacy",
            "traffic_type",
        }:
            raise ValueError("unknown server fact")
        if value.get("schema_version") != 1:
            raise ValueError("unknown fact version")
        if "query" in value.get("legacy", {}):
            raise ValueError("query belongs to private context")
        return value


class SearchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search: SearchFactRecord
    context: SearchContext

    def consistent(self) -> bool:
        return self.search.search_id == self.context.search_id


class JournalEvent(Event):
    received_at: datetime
    app_version: str = Field(max_length=100)
    traffic_type: Literal["declared_technical", "suspected_bot", "unclassified"]
    private_context: EventContextRecord

    @field_validator("received_at")
    @classmethod
    def server_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("server timestamp needs timezone")
        return value

    def consistent(self) -> bool:
        return self.event_id == self.private_context.event_id
