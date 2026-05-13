from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Select, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import AccessStatus, AlertStatus, NotificationStatus, UserRole
from app.db.models import Alert, AlertEvent, Asset, PriceSnapshot, ProviderLink, User


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
    return await get_user_by_id(session, user_id)


async def get_user_by_id(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise LookupError(f"user {user_id} not found")
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


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


async def get_stats(session: AsyncSession) -> dict[str, int]:
    users = await session.scalar(select(func.count()).select_from(User))
    active_alerts = await session.scalar(
        select(func.count()).select_from(Alert).where(Alert.status == AlertStatus.ACTIVE.value)
    )
    watched_assets = await session.scalar(
        select(func.count(func.distinct(Alert.asset_id))).where(Alert.status == AlertStatus.ACTIVE.value)
    )
    return {
        "users": int(users or 0),
        "active_alerts": int(active_alerts or 0),
        "watched_assets": int(watched_assets or 0),
    }


async def upsert_asset_from_candidate(session: AsyncSession, candidate) -> Asset:
    stmt = (
        insert(Asset)
        .values(
            type=candidate.type.value,
            chain=candidate.chain,
            symbol=candidate.symbol.upper(),
            name=candidate.name,
            contract_address=candidate.contract_address,
            provider=candidate.provider,
            provider_asset_id=candidate.provider_asset_id,
            extra=candidate.metadata,
        )
        .on_conflict_do_update(
            constraint="uq_assets_provider_asset",
            set_={
                "chain": candidate.chain,
                "symbol": candidate.symbol.upper(),
                "name": candidate.name,
                "contract_address": candidate.contract_address,
                Asset.extra: candidate.metadata,
                "updated_at": func.now(),
            },
        )
        .returning(Asset.id)
    )
    asset_id = await session.scalar(stmt)
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise LookupError(f"asset {asset_id} not found")
    for kind, url in candidate.links.items():
        await upsert_provider_link(session, asset_id=asset.id, kind=kind, url=url)
    return asset


async def upsert_provider_link(session: AsyncSession, *, asset_id: int, kind: str, url: str) -> None:
    stmt = (
        insert(ProviderLink)
        .values(asset_id=asset_id, kind=kind, url=url)
        .on_conflict_do_update(
            constraint="uq_provider_links_asset_kind",
            set_={"url": url},
        )
    )
    await session.execute(stmt)


async def latest_snapshot(session: AsyncSession, asset_id: int) -> PriceSnapshot | None:
    return await session.scalar(
        select(PriceSnapshot)
        .where(PriceSnapshot.asset_id == asset_id)
        .order_by(PriceSnapshot.created_at.desc())
        .limit(1)
    )


async def create_snapshot(
    session: AsyncSession,
    *,
    asset_id: int,
    price_usd: Decimal,
    source: str,
    raw: dict,
    price_native: Decimal | None = None,
    native_symbol: str | None = None,
) -> PriceSnapshot:
    snapshot = PriceSnapshot(
        asset_id=asset_id,
        price_usd=price_usd,
        price_native=price_native,
        native_symbol=native_symbol,
        source=source,
        raw=raw,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def create_alert(
    session: AsyncSession,
    *,
    user_id: int,
    asset_id: int,
    alert_type: str,
    baseline_price: Decimal,
    threshold_value: Decimal,
    direction: str,
) -> Alert:
    alert = Alert(
        user_id=user_id,
        asset_id=asset_id,
        type=alert_type,
        baseline_price=baseline_price,
        threshold_value=threshold_value,
        direction=direction,
    )
    session.add(alert)
    await session.flush()
    return alert


async def active_alerts_for_user(session: AsyncSession, telegram_id: int) -> Sequence[Alert]:
    result = await session.scalars(
        select(Alert)
        .join(User)
        .options(selectinload(Alert.asset).selectinload(Asset.links))
        .where(
            User.telegram_id == telegram_id,
            Alert.status == AlertStatus.ACTIVE.value,
        )
        .order_by(Alert.created_at.desc())
    )
    return result.all()


async def delete_active_alert_for_user(session: AsyncSession, *, telegram_id: int, alert_id: int) -> bool:
    alert = await session.scalar(
        select(Alert)
        .join(User)
        .where(
            Alert.id == alert_id,
            User.telegram_id == telegram_id,
            Alert.status == AlertStatus.ACTIVE.value,
        )
    )
    if alert is None:
        return False

    alert.status = AlertStatus.DELETED.value
    await session.flush()
    return True


async def active_alerts_for_asset(session: AsyncSession, asset_id: int) -> Sequence[Alert]:
    result = await session.scalars(
        select(Alert)
        .options(selectinload(Alert.user), selectinload(Alert.asset).selectinload(Asset.links))
        .where(Alert.asset_id == asset_id, Alert.status == AlertStatus.ACTIVE.value)
    )
    return result.all()


async def active_watched_assets(session: AsyncSession) -> Sequence[Asset]:
    result = await session.scalars(
        select(Asset)
        .join(Alert)
        .options(selectinload(Asset.links))
        .where(Alert.status == AlertStatus.ACTIVE.value)
        .distinct()
    )
    return result.all()


async def mark_alert_triggered(session: AsyncSession, alert_id: int) -> None:
    await session.execute(
        update(Alert)
        .where(Alert.id == alert_id, Alert.status == AlertStatus.ACTIVE.value)
        .values(status=AlertStatus.TRIGGERED.value, triggered_at=datetime.now(UTC))
    )


async def create_alert_event(
    session: AsyncSession,
    *,
    alert_id: int,
    snapshot_id: int,
    direction: str,
    percent_change: Decimal,
) -> AlertEvent:
    event = AlertEvent(
        alert_id=alert_id,
        snapshot_id=snapshot_id,
        direction=direction,
        percent_change=percent_change,
        notification_status=NotificationStatus.QUEUED.value,
    )
    session.add(event)
    await session.flush()
    return event


async def queued_alert_events(session: AsyncSession, limit: int = 25) -> Sequence[AlertEvent]:
    stmt: Select[tuple[AlertEvent]] = (
        select(AlertEvent)
        .options(
            selectinload(AlertEvent.alert).selectinload(Alert.user),
            selectinload(AlertEvent.alert).selectinload(Alert.asset).selectinload(Asset.links),
            selectinload(AlertEvent.snapshot),
        )
        .where(AlertEvent.notification_status == NotificationStatus.QUEUED.value)
        .order_by(AlertEvent.created_at.asc())
        .limit(limit)
    )
    result = await session.scalars(stmt)
    return result.all()
