"""
py-auth-sqlalchemy: SQLAlchemy adapter for py-auth database persistence.

This package provides a SQLAlchemy-based adapter implementation for the py-auth
authentication library, enabling database persistence for users, accounts, and sessions
using SQLAlchemy ORM with async support. It includes the SqlAlchemyAdapter class for
database operations and UTCDateTime type for timezone-aware datetime handling.
"""


from .core import SqlAlchemyAdapter
from .utc_datetime import UTCDateTime

__all__ = ["SqlAlchemyAdapter", "UTCDateTime"]
__version__ = "0.0.2"
