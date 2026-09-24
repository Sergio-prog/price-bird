from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.enums import AccessStatus, UserRole
from app.db.models import User


async def upsert_telegram_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    language_code: str | None,
) -> User:
    stmt = (
        insert(User)
        .values(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )
        .on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_={
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "language_code": language_code,
                "updated_at": func.now(),
            },
        )
        .returning(User.id)
    )
    user_id = await session.scalar(stmt)
    user = await get_user_by_id(session, user_id)
    if settings.public_access_enabled and user.access_status == AccessStatus.PENDING.value:
        user.access_status = AccessStatus.ACTIVE.value
        await session.flush()
    return user


async def get_user_by_id(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise LookupError(f"user {user_id} not found")
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_user_language(session: AsyncSession, telegram_id: int) -> str | None:
    return await session.scalar(select(User.language).where(User.telegram_id == telegram_id))


async def ensure_admin(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None = None,
) -> User:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            role=UserRole.ADMIN.value,
            access_status=AccessStatus.ACTIVE.value,
        )
        session.add(user)
        await session.flush()
        return user

    user.role = UserRole.ADMIN.value
    user.access_status = AccessStatus.ACTIVE.value
    if username:
        user.username = username
    await session.flush()
    return user


async def set_user_access(
    session: AsyncSession,
    *,
    telegram_id: int,
    access_status: AccessStatus,
    role: UserRole | None = None,
) -> User:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id, access_status=access_status.value)
        session.add(user)
    else:
        user.access_status = access_status.value
    if role is not None:
        user.role = role.value
    await session.flush()
    return user


def has_bot_access(user: User | None) -> bool:
    return user is not None and user.access_status == AccessStatus.ACTIVE.value


def is_admin(user: User | None) -> bool:
    return has_bot_access(user) and user.role == UserRole.ADMIN.value


async def list_users(session: AsyncSession, limit: int = 50) -> Sequence[User]:
    result = await session.scalars(select(User).order_by(User.created_at.desc()).limit(limit))
    return result.all()


async def broadcast_recipient_ids(session: AsyncSession) -> list[int]:
    result = await session.scalars(
        select(User.telegram_id).where(User.access_status != AccessStatus.SUSPENDED.value).order_by(User.id)
    )
    return list(result.all())


async def count_broadcast_recipients(session: AsyncSession) -> int:
    count = await session.scalar(
        select(func.count()).select_from(User).where(User.access_status != AccessStatus.SUSPENDED.value)
    )
    return count or 0


async def find_users_by_refs(
    session: AsyncSession,
    *,
    telegram_ids: set[int],
    usernames: set[str],
) -> Sequence[User]:
    conditions = []
    if telegram_ids:
        conditions.append(User.telegram_id.in_(telegram_ids))
    if usernames:
        conditions.append(func.lower(User.username).in_(usernames))
    if not conditions:
        return []
    result = await session.scalars(select(User).where(or_(*conditions)).order_by(User.id))
    return result.all()
