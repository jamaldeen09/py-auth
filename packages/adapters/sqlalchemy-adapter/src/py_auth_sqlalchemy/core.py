from .utils import handle_db_errors, validate_async_engine, validate_sqlalchemy_model

from typing import Any, Dict, Type
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from py_auth.exceptions import AdapterError, RecordNotFoundError

class SqlAlchemyAdapter:
    """SQLAlchemy ORM adapter for py-auth.

    Provides asynchronous session persistence using SQLAlchemy 2.0.
    User lookup and creation is handled entirely within the authorize()
    callback of your CredentialsProvider.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        session_model: Type[Any],
        user_model: Type[Any] | None = None,
        account_model: Type[Any] | None = None,
    ):
        self.session_model = validate_sqlalchemy_model(
            model=session_model,
            model_name="Session",
            required_cols={
                "id",
                "session_token_hash",
                "user_id",
                "expires",
                "csrf_token",
            },
        )

        if user_model:
            self.user_model = validate_sqlalchemy_model(
                model=user_model,
                model_name="User",
                required_cols={
                   "id",
                   "email",
                   "name",
                   "image",
                }
            )

        if account_model:
            self.account_model = validate_sqlalchemy_model(
                model=account_model,
                model_name="Account",
                required_cols={
                    "id",
                    "user_id",
                    "type",
                    "provider",
                    "provider_account_id",
                    "access_token",
                    "refresh_token",
                    "expires_at",
                    "token_type",
                    "scope",
                    "id_token",
                    "session_state"
                }
            )


        self.engine = validate_async_engine(engine=engine)
        self.session_maker = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    def _row_to_dict(self, instance: Any) -> Dict[str, Any] | None:
        """Convert ORM instance to a dictionary using its table column names."""
        if instance is None:
            return None
        cols = [c.name for c in instance.__table__.columns]
        return {name: getattr(instance, name) for name in cols}
    
    async def get_or_create_user_and_link_account(
        self, 
        email: str, 
        user_data: Dict[str, Any], 
        account_data: Dict[str, Any]
    ) -> Dict[str, Any] | None:
        
        if not self.user_model:
            raise AdapterError(
                "Attempted to call 'get_or_create_user_and_link_account', "
                "but 'user_model' is not configured."
            )

        if not self.account_model:
            raise AdapterError(
                "Attempted to call 'get_or_create_user_and_link_account', "
                "but 'account_model' is not configured."
            )

        async with handle_db_errors(operation="get_or_create_user_and_link_account"):
            async with self.session_maker() as session:
                async with session.begin():
                    stmt = (select(self.user_model).where(self.user_model.email == email).with_for_update())

                    result = await session.execute(stmt)
                    user = result.scalars().first()

                    if user is None:
                        user = self.user_model(**user_data)
                        session.add(user)
                        await session.flush()

                    account = self.account_model(user_id=user.id,**account_data)
                    session.add(account)
                    await session.flush()
                    await session.refresh(user)

                return self._row_to_dict(user)
    
    
    async def link_account(self,account_data: Dict[str, Any],) -> Dict[str, Any] | None:
        """Create and persist a new account record."""
        if not self.account_model:
            raise AdapterError(
              "Attempted to call 'link_account', but 'account_model' is not configured in the adapter."
            )

        async with handle_db_errors(operation="link_account"):
            async with self.session_maker() as session:
                async with session.begin():
                    account = self.account_model(**account_data)
                    session.add(account)
                    await session.flush()
                    await session.refresh(account)
                return self._row_to_dict(account)
            
    async def unlink_account(self,provider: str, provider_account_id: str) -> None:
        """Delete an existing account record linked to a provider."""

        if not self.account_model:
            raise AdapterError(
                "Attempted to call 'unlink_account', but 'account_model' "
                "is not configured in the adapter."
            )

        async with handle_db_errors(operation="unlink_account"):
            async with self.session_maker() as session:
                async with session.begin():
                    stmt = (
                        delete(self.account_model)
                        .where(
                            self.account_model.provider == provider,
                            self.account_model.provider_account_id == provider_account_id,
                        )
                    )

                    await session.execute(stmt)

    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any] | None:
        """Create and persist a new session record."""
        async with handle_db_errors(operation="create_session"):
            async with self.session_maker() as session:
                async with session.begin():
                    s = self.session_model(**session_data)
                    session.add(s)
                    await session.flush()
                    await session.refresh(s)  
                return self._row_to_dict(s)

    async def update_session(
        self, session_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any] | None:
        async with handle_db_errors(operation="update_session"):
            async with self.session_maker() as session:
                async with session.begin():
                    stmt = (
                        select(self.session_model)
                        .where(self.session_model.id == session_id)
                        .with_for_update()
                    )
                    result = await session.execute(stmt)
                    s = result.scalars().first()
                    if s is None:
                        return None
                    for k, v in updates.items():
                        if hasattr(s, k) and k != "id":
                            setattr(s, k, v)
                await session.refresh(s)
                return self._row_to_dict(s)

    async def get_session_by_session_token_hash(
        self, session_token_hash: str
    ) -> Dict[str, Any] | None:
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

    async def delete_session_by_session_token_hash(
        self, session_token_hash: str
    ) -> None:
        """Delete a session record by its hashed session token."""
        async with handle_db_errors(operation="delete_session_by_session_token_hash"):
            async with self.session_maker() as session:
                async with session.begin():
                    stmt = delete(self.session_model).where(
                        self.session_model.session_token_hash == session_token_hash
                    )
                    await session.execute(stmt)

    async def delete_session(self, session_id: Any) -> None:
        """Delete a session record by its unique identifier."""
        async with handle_db_errors(operation="delete_session_by_id"):
            async with self.session_maker() as session:
                async with session.begin():
                    stmt = delete(self.session_model).where(
                        self.session_model.id == session_id
                    )
                    await session.execute(stmt)
