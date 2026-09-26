"""SQLAlchemy datetime type for consistent UTC-aware datetime handling across database backends."""

from sqlalchemy import DateTime
from datetime import datetime, timezone
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.types import TypeDecorator

class UTCDateTime(TypeDecorator):
    """SQLAlchemy datetime type that provides consistent UTC-aware datetimes across supported database backends."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(
                DATETIME(fsp=6)
            )
        
        if dialect.name == "sqlite":
            return dialect.type_descriptor(
                DateTime()
            )

        return dialect.type_descriptor(
            DateTime(timezone=True)
        )

    def process_bind_param(
        self,
        value: datetime | None,
        dialect,
    ):
        if value is None:
            return None

        if value.tzinfo is None:
            raise ValueError("UTCDateTime requires a timezone-aware datetime")

        value = value.astimezone(timezone.utc)

        if dialect.name in ("mysql", "sqlite"):
            return value.replace(tzinfo=None)

        return value

    def process_result_value(
        self,
        value: datetime | None,
        dialect,
    ):
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)