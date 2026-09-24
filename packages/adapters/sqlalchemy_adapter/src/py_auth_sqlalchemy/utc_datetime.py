
from sqlalchemy import DateTime
from datetime import datetime, timezone
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.types import TypeDecorator

class UTCDateTime(TypeDecorator):
    """
    SQLAlchemy datetime type that provides consistent UTC-aware datetimes
    across supported database backends.

    Python-side behavior:
        Values are always expected to be timezone-aware and are normalized
        to UTC before being stored.

    PostgreSQL:
        Uses a timezone-aware timestamp and preserves the UTC timezone.

    MySQL:
        MySQL DATETIME does not preserve timezone information. Values are
        therefore converted to UTC and stored as naive UTC datetimes.
        When read back, the UTC timezone is restored.

    SQLite:
        SQLite does not have a native timezone-aware datetime type. Values
        are therefore handled like MySQL: stored as naive UTC datetimes and
        returned to Python as timezone-aware UTC datetimes.

    This allows the rest of py-auth to consistently work with timezone-aware
    UTC datetimes without needing database-specific datetime handling.
    """

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