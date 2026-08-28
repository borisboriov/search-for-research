"""SQLAlchemy models. PostgreSQL-compatible types only (SQLite is just the default file DB)."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    openalex_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    ror_id: Mapped[str | None] = mapped_column(String(64))
    name_en: Mapped[str] = mapped_column(String(512))
    # OpenAlex has no dedicated Russian name field; taken from display_name_alternatives
    # (first Cyrillic entry) when present.
    name_ru: Mapped[str | None] = mapped_column(String(512))
    country: Mapped[str | None] = mapped_column(String(8))

    authors: Mapped[list["Author"]] = relationship(back_populates="institution")


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    openalex_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    orcid: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(512))
    last_known_institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id"), index=True
    )
    works_count: Mapped[int] = mapped_column(Integer, default=0)
    cited_by_count: Mapped[int] = mapped_column(Integer, default=0)
    h_index: Mapped[int | None] = mapped_column(Integer)
    i10_index: Mapped[int | None] = mapped_column(Integer)
    is_supervisor_candidate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    institution: Mapped[Institution | None] = relationship(back_populates="authors")
    works: Mapped[list["Work"]] = relationship(back_populates="author")
    topics: Mapped[list["AuthorTopic"]] = relationship(back_populates="author")
    profile: Mapped["SupervisorProfile | None"] = relationship(back_populates="author")


class Work(Base):
    __tablename__ = "works"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    openalex_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # SFR-0: single "whose profile this work counts towards" link (SPEC §3),
    # not full many-to-many authorship.
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    publication_year: Mapped[int | None] = mapped_column(Integer)
    abstract_text: Mapped[str | None] = mapped_column(Text)
    topics: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    cited_by_count: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str | None] = mapped_column(String(16))
    is_recent: Mapped[bool] = mapped_column(Boolean, default=False)

    author: Mapped[Author] = relationship(back_populates="works")


class AuthorTopic(Base):
    __tablename__ = "author_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), index=True)
    topic_name: Mapped[str] = mapped_column(String(512))
    score: Mapped[float] = mapped_column(Float, default=0.0)

    author: Mapped[Author] = relationship(back_populates="topics")


class SupervisorProfile(Base):
    __tablename__ = "supervisor_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), unique=True, index=True)
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"))
    profile_text: Mapped[str] = mapped_column(Text)
    n_works: Mapped[int] = mapped_column(Integer, default=0)
    n_abstracts: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    author: Mapped[Author] = relationship(back_populates="profile")
