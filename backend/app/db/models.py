"""ORM models. Quiz/progress tables are added in later phases."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db.database import Base

STATUS_PROCESSING = "processing"
STATUS_INDEXED = "indexed"
STATUS_FAILED = "failed"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Store UTC datetimes; SQLite drops tzinfo, so re-attach it on read."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):  # noqa: ANN001
        return None if value is None else value.replace(tzinfo=timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    # Stable id derived from the file's SHA-256 ("doc_" + first 16 hex chars),
    # so uploading identical bytes twice cannot create a second index entry.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))  # sanitized display name
    file_type: Mapped[str] = mapped_column(String(16))  # pdf | txt | md
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    stored_filename: Mapped[str] = mapped_column(String(64))  # internal, never user-supplied
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=STATUS_PROCESSING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    indexed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
