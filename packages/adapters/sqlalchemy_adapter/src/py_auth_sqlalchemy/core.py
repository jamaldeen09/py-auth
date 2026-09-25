from ._utils import handle_db_errors, validate_async_engine, validate_sqlalchemy_model

from typing import Any, Dict, Type, List
from sqlalchemy import delete, select, and_
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from py_auth.exceptions import AdapterError

class SqlAlchemyAdapter:
    """
    SQLAlchemy adapter implementation for py-auth database operations.

    This adapter provides database persistence for py-auth authentication using SQLAlchemy async models.
    It implements the PyAuthAdapterProtocol interface to handle user, account, and session management
    through SQLAlchemy ORM with async support.

    The adapter requires a session_model for session management, with optional user_model and account_model
    for user account and OAuth account linking. All models are validated to ensure they contain the required
    columns for py-auth operations.
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
            required_columns={
                "id",
                "session_token_hash",
                "user_id",
                "expires",
            },
        )

        if user_model:
            self.user_model = validate_sqlalchemy_model(
                model=user_model,
                model_name="User",
                required_columns={
                   "id",
                   "email",
                   "name",
                   "image",
                   "password_hash"
                }
            )

        if account_model:
            self.account_model = validate_sqlalchemy_model(
                model=account_model,
                model_name="Account",
                required_columns={
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




    async def create_user(self, user_data: dict) -> Dict[str, Any] | None:
        if not self.user_model:
            raise AdapterError(
                "Attempted to call 'create_user', "
                "but 'user_model' is not configured."
            )
        
        async with handle_db_errors(operation="create_user"):
            async with self.session_maker() as session:
                async with session.begin():
                    user = self.user_model(**user_data)
                    session.add(user)
                return self._row_to_dict(user)
            
    async def get_user(self, user_id: str) -> Dict[str, Any] | None:
        if not self.user_model:
            raise AdapterError(
                "Attempted to call 'get_user', "
                "but 'user_model' is not configured."
            )
        
        async with handle_db_errors(operation="get_user"):
            async with self.session_maker() as session:
                stmt = select(self.user_model).where(self.user_model.id == user_id)
                result = await session.execute(stmt)
                user = result.scalars().first()
                return self._row_to_dict(user)
            
    async def get_user_by_email(self, email: str) -> Dict[str, Any] | None:
        if not self.user_model:
            raise AdapterError(
                "Attempted to call 'get_user_by_email', "
                "but 'user_model' is not configured."
            )
          
        async with handle_db_errors(operation="get_user_by_email"):
            async with self.session_maker() as session:
                stmt = select(self.user_model).where(self.user_model.email == email)
                result = await session.execute(stmt)
                user = result.scalars().first()
                return self._row_to_dict(user)
    
    async def update_user(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any] | None:
        if not self.user_model:
            raise AdapterError(
                "Attempted to call 'update_user', "
                "but 'user_model' is not configured."
            )
        
        async with handle_db_errors(operation="update_user"):
            async with self.session_maker() as session:
                async with session.begin():
                    result = await session.execute(
                        select(self.user_model)
                        .where(self.user_model.id == user_id)
                        .with_for_update()
                    )
                    user = result.scalars().first()

                    if user is None:
                        return None
                    
                    for key, value in updates.items():
                        if hasattr(user, key) and key != "id":
                            setattr(user, key, value)

                await session.refresh(user)
                return self._row_to_dict(user)
            
    async def delete_user(self, user_id: str) -> None:
        if not self.user_model:
            raise AdapterError(
                "Attempted to call 'delete_user', "
                "but 'user_model' is not configured."
            )

        async with handle_db_errors(operation="delete_user"): 
            async with self.session_maker() as session:
                async with session.begin():
                    user = await session.get(self.user_model, user_id)
                    if user is None:
                        return
                    await session.delete(user)


        # 
    



    async def list_accounts_for_user(self, user_id: str) -> List[(Dict[str, Any] | None)]:
        if not self.account_model:
            raise AdapterError(
                "Attempted to call 'list_accounts_for_user', "
                "but 'account_model' is not configured."
            )
        async with handle_db_errors(operation="list_accounts_for_user"):
            async with self.session_maker() as session:
                stmt = select(self.account_model).where(self.account_model.user_id == user_id)
                result = await session.execute(stmt)
                return [self._row_to_dict(a) for a in result.scalars().all()]
            
    async def link_account(self, account_data: Dict[str, Any]) -> Dict[str, Any] | None:
        if not self.account_model:
            raise AdapterError(
                "Attempted to call 'link_account', "
                "but 'account_model' is not configured."
            )
        
        async with handle_db_errors(operation="link_account"):
            async with self.session_maker() as session:
                async with session.begin():
                    account = self.account_model(**account_data)
                    session.add(account)
                    await session.flush()
                return self._row_to_dict(account)
            
    async def unlink_account(self, provider: str, provider_account_id: str) -> None:
        if not self.account_model:
            raise AdapterError(
                "Attempted to call 'unlink_account', "
                "but 'account_model' is not configured."
            )
         
        async with self.session_maker() as session:
            async with session.begin():
                stmt = (
                    delete(self.account_model)
                    .where(
                        and_(
                            self.account_model.provider == provider,
                            self.account_model.provider_account_id == provider_account_id,
                        )
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
                return self._row_to_dict(s)
            
    async def list_sessions_for_user(self, user_id: str) -> List[(Dict[str, Any] | None)]:
        async with handle_db_errors(operation="list_sessions_for_user"):
            async with self.session_maker() as session:
                stmt = select(self.session_model).where(self.session_model.user_id == user_id)
                result = await session.execute(stmt)
                return [self._row_to_dict(s) for s in result.scalars().all()]

    async def update_session(
        self, session_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any] | None:
        async with handle_db_errors(operation="update_session"):
            async with self.session_maker() as session:
                async with session.begin():
                    result = await session.execute(
                        select(self.session_model)
                        .where(self.session_model.id == session_id)
                        .with_for_update()
                    )
                    _session = result.scalars().first()

                    if _session is None:
                        return None
                    
                    for key, value in updates.items():
                        if hasattr(_session, key) and key != "id":
                            setattr(_session, key, value)

                await session.refresh(_session)
                return self._row_to_dict(_session)

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




    async def get_or_create_user_and_link_account(self, email: str, user_data: Dict[str, Any], account_data: Dict[str, Any]) -> Dict[str, Any] | None:
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
                    result = await session.execute(select(self.user_model).where(self.user_model.email == email))
                    user = result.scalar_one_or_none()

                    if user is None:
                        user = self.user_model(**user_data)
                        session.add(user)
                        await session.flush()

                    account = self.account_model(**account_data,user_id=user.id)
                    session.add(account)
                    await session.flush()

                    user_dict = self._row_to_dict(user)
                    account_dict = self._row_to_dict(account)
                    return {"user":user_dict,"account":account_dict}
    
