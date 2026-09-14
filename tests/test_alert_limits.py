from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.alerts import limits
from app.alerts.limits import AlertLimitReached, ensure_alert_capacity
from app.db.enums import AlertLimitKind

TOKEN_LIMIT = SimpleNamespace(asset_kind="token", max_watched_assets=2, max_active_alerts=10, default_user_max_alerts=3)


def _patch_repo(monkeypatch, *, user_alerts=0, total_alerts=0, watched_assets=0, asset_watched=False) -> None:
    async def count_limited_alerts(session, kind, *, user_id=None):
        return total_alerts if user_id is None else user_alerts

    monkeypatch.setattr(limits.repo, "get_alert_limit", AsyncMock(return_value=TOKEN_LIMIT))
    monkeypatch.setattr(limits.repo, "user_max_alerts", AsyncMock(return_value=TOKEN_LIMIT.default_user_max_alerts))
    monkeypatch.setattr(limits.repo, "count_limited_alerts", count_limited_alerts)
    monkeypatch.setattr(limits.repo, "count_watched_assets", AsyncMock(return_value=watched_assets))
    monkeypatch.setattr(limits.repo, "is_asset_watched", AsyncMock(return_value=asset_watched))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("counts", "key"),
    [
        ({"user_alerts": 3}, "limit-user-token"),
        ({"total_alerts": 10}, "limit-global-alerts-token"),
        ({"watched_assets": 2}, "limit-global-assets-token"),
    ],
)
async def test_rejects_alert_over_limit(monkeypatch, counts, key) -> None:
    _patch_repo(monkeypatch, **counts)

    with pytest.raises(AlertLimitReached) as error:
        await ensure_alert_capacity(object(), user_id=1, asset=SimpleNamespace(id=5, type="cex_symbol"))

    assert error.value.key == key


@pytest.mark.asyncio
async def test_allows_new_alert_for_already_watched_asset_at_asset_capacity(monkeypatch) -> None:
    _patch_repo(monkeypatch, user_alerts=2, total_alerts=9, watched_assets=2, asset_watched=True)

    await ensure_alert_capacity(object(), user_id=1, asset=SimpleNamespace(id=5, type="token"))


def test_limit_kind_groups_asset_types() -> None:
    assert AlertLimitKind.for_asset_type("nft_collection") is AlertLimitKind.NFT
    assert AlertLimitKind.for_asset_type("token") is AlertLimitKind.TOKEN
    assert AlertLimitKind.for_asset_type("cex_symbol") is AlertLimitKind.TOKEN
