from contextlib import asynccontextmanager
from typing import Any

from py_auth.exceptions import (
    AdapterError,
    DuplicateEntryError,
    ForeignKeyViolationError,
    PyAuthError,
    RecordNotFoundError,
)
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncEngine


def validate_async_engine(engine: object) -> AsyncEngine:
    """Validate that the engine is an asynchronous SQLAlchemy AsyncEngine
    and uses a supported asynchronous database driver.
    """
    if not isinstance(engine, AsyncEngine):
        raise TypeError(
            "Invalid database engine. py-auth requires an asynchronous SQLAlchemy "
            "'AsyncEngine' (created via create_async_engine)."
        )

    # Inspect the driver prefix from the engine's URL object
    supported_drivers = ("asyncpg", "aiomysql", "aiosqlite")
    driver = engine.url.get_driver_name()

    if driver not in supported_drivers:
        raise AdapterError(
            f"Unsupported database driver '{driver}'. "
            f"py-auth requires one of the following async drivers: {supported_drivers}"
        )
    return engine


def validate_sqlalchemy_model(
    model: type[Any],
    required_cols: set[str],
    model_name: str | None = None,
) -> type[Any]:
    """Validate that the provided class is a valid SQLAlchemy declarative model
    and defines all required py-auth columns.
    """
    if model is None:
        name = model_name or "Model"
        raise AdapterError(f"'{name}' model is required and cannot be None.")

    display_name = getattr(model, "__name__", None) or model_name or "Model"

    try:
        mapper = inspect(model)
        col_names = {c.key for c in mapper.columns}
    except Exception as e:
        raise AdapterError(
            f"Provided '{display_name}' must be a valid SQLAlchemy model class: {e}"
        )

    if not required_cols.issubset(col_names):
        missing = sorted(required_cols - col_names)
        raise AdapterError(
            f"Custom {display_name} model is missing required py-auth columns: {missing}. "
            "Extra custom columns are allowed, but these base columns are mandatory."
        )
    return model


@asynccontextmanager
async def handle_db_errors(operation: str):
    """Context manager for the SQLAlchemy adapter to intercept database-specific
    exceptions and translate them into py-auth core exceptions.
    """
    try:
        yield
    except IntegrityError as e:
        error_msg = str(e.orig or e).lower()
        if "foreign key" in error_msg or "violates foreign key" in error_msg:
            raise ForeignKeyViolationError(
                f"Failed to complete operation '{operation}': the referenced record does not exist."
            ) from e
        elif "unique" in error_msg or "duplicate" in error_msg:
            raise DuplicateEntryError(
                f"Failed to complete operation '{operation}': a record with this unique value already exists."
            ) from e
        raise PyAuthError(
            f"Database integrity error occurred in operation '{operation}': {e}"
        ) from e

    except NoResultFound as e:
        raise RecordNotFoundError(
            f"Failed to complete operation '{operation}': the requested record was not found."
        ) from e

    except PyAuthError:
        raise
    except Exception as e:
        raise PyAuthError(
            f"An unexpected database error occurred in operation '{operation}': {e}"
        ) from e
