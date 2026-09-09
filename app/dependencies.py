from sqlalchemy.ext.asyncio import AsyncSession
from config import get_session_factory


async def get_db() -> AsyncSession:  # type: ignore[return]
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
