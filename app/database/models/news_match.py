"""
News Match Model

Represents the relationship between a news
article and one or more facilities.

Stores the entity matching results.
"""

from __future__ import annotations

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


class NewsMatch(Base):

    __tablename__ = "news_matches"

    __table_args__ = (
        {
            "schema": "iris_core",
        },
    )

    # ======================================================
    # Primary Key
    # ======================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # ======================================================
    # Relationships
    # ======================================================

    article_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "iris_core.news_articles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    facility_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "iris_core.facilities.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # ======================================================
    # Extracted Intelligence
    # ======================================================

    company: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    facility_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    match_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    match_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # ======================================================
    # Audit
    # ======================================================

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ======================================================
    # Relationships
    # ======================================================

    article: Mapped["NewsArticle"] = relationship(
        "NewsArticle",
        back_populates="matches",
    )

    facility: Mapped["Facility"] = relationship(
        "Facility",
        back_populates="news_matches",
    )