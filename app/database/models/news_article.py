"""
News Article Model

Represents a raw news article collected from
RSS feeds and external data sources.

This table stores the original article before
entity matching and rule-based signal extraction.

Author:
NRW BI Platform
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    DateTime,
    String,
    Text,
    func,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


# ==========================================================
# News Article
# ==========================================================


class NewsArticle(Base):

    __tablename__ = "news_articles"

    __table_args__ = (
        {
            "schema": "iris_core",
        },
    )

    # ------------------------------------------------------
    # Primary Key
    # ------------------------------------------------------

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    # ------------------------------------------------------
    # Source Information
    # ------------------------------------------------------

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
    )

    # ------------------------------------------------------
    # Article
    # ------------------------------------------------------

    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    # ------------------------------------------------------
    # Publication
    # ------------------------------------------------------

    published_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ------------------------------------------------------
    # Processing
    # ------------------------------------------------------

    processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # ------------------------------------------------------
    # Audit
    # ------------------------------------------------------

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ------------------------------------------------------
    # Relationships
    # ------------------------------------------------------

    matches: Mapped[list["NewsMatch"]] = relationship(
        "NewsMatch",
        back_populates="article",
        cascade="all, delete-orphan",
    )