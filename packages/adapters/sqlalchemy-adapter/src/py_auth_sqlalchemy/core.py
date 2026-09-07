
from .utils import handle_db_errors, validate_async_engine, validate_sqlalchemy_model

from typing import Any, Dict, Optional, Type
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

class SqlAlchemyAdapter:
    """SQLAlchemy ORM adapter for py-auth.

    Provides asynchronous persistence for users and sessions using SQLAlchemy 2.0.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        session_model: Type[Any] = None,
    ):
        self.session_model = validate_sqlalchemy_model(
            model=session_model,
            model_name="Session",
            required_cols={"id", "session_token_hash", "user_id", "expires", "csrf_token"},
        )

        self.engine = validate_async_engine(engine=engine)
        self.session_maker = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    def _row_to_dict(self, instance: Any) -> Optional[Dict[str, Any]]:
        """Convert ORM instance to a dictionary using its table column names."""
        if instance is None:
            return None
        cols = [c.name for c in instance.__table__.columns]
        return {name: getattr(instance, name) for name in cols}
 
    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create and persist a new session record."""
        async with handle_db_errors(operation="create_session"):
            async with self.session_maker() as session:
                async with session.begin():
                    s = self.session_model(**session_data)
                    session.add(s)
                await session.refresh(s)
                return self._row_to_dict(s)

    async def get_session_by_session_token_hash(
        self, session_token_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a session record by its hashed session token."""
        async with handle_db_errors(operation="get_session_by_session_token_hash"):
            async with self.session_maker() as session:
                stmt = select(self.session_model).where(
                    self.session_model.session_token_hash == session_token_hash
                )
                result = await session.execute(stmt)
                s = result.scalar_one_or_none()
                if not s:
                    return None
                return self._row_to_dict(s)

    async def delete_session_by_session_token_hash(self, session_token_hash: str) -> None:
        """Delete a session record by its hashed session token."""
        async with handle_db_errors(operation="delete_session_by_session_token_hash"):
            async with self.session_maker() as session:
                async with session.begin():
                    stmt = delete(self.session_model).where(
                        self.session_model.session_token_hash == session_token_hash
                    )
                    await session.execute(stmt)

    async def delete_session_by_id(self, session_id: Any) -> None:
        """Delete a session record by its unique identifier."""
        async with handle_db_errors(operation="delete_session_by_id"):
            async with self.session_maker() as session:
                async with session.begin():
                    stmt = delete(self.session_model).where(
                        self.session_model.id == session_id
                    )
                    await session.execute(stmt)
