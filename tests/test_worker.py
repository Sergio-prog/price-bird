from decimal import Decimal
from types import SimpleNamespace

import pytest

from app import worker
from app.db.enums import AssetType
from app.providers.base import PriceQuote


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, tuple[str, int]] = {}
        self.locked = False

    async def mget(self, keys: list[str]) -> list[str | None]:
        return [self.store[key][0] if key in self.store else None for key in keys]

    async def set(self, key: str, value: str, ex: int) -> None:
        self.store[key] = (value, ex)

    def lock(self, name: str, timeout: int):
        return FakeLock(self)


class FakeLock:
    def __init__(self, client: FakeRedis) -> None:
        self.client = client

    async def acquire(self, blocking: bool) -> bool:
        if self.client.locked:
            return False
        self.client.locked = True
        return True

    async def release(self) -> None:
        self.client.locked = False


def _asset(asset_id: int, asset_type: AssetType = AssetType.TOKEN) -> SimpleNamespace:
    return SimpleNamespace(id=asset_id, type=asset_type.value, provider="fake", symbol=f"A{asset_id}")


@pytest.mark.asyncio
async def test_nft_assets_wait_for_their_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker.settings, "price_refresh_interval_seconds", 45)
    monkeypatch.setattr(worker.settings, "nft_refresh_interval_seconds", 300)
    client = FakeRedis()
    token = _asset(1)
    nft = _asset(2, AssetType.NFT_COLLECTION)

    assert await worker.due_assets(client, [token, nft]) == [token, nft]

    await worker.mark_refreshed(client, token)
    await worker.mark_refreshed(client, nft)

    assert client.store == {"asset_refresh:done:2": ("1", 278)}
    assert await worker.due_assets(client, [token, nft]) == [token]


@pytest.mark.asyncio
async def test_refresh_provider_evaluates_batched_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker, "REFRESH_CHUNK_SIZE", 2)
    batches: list[list[int]] = []
    evaluated: list[int] = []

    class FakeProvider:
        name = "fake"

        async def get_prices(self, assets):
            batches.append([asset.id for asset in assets])
            return {asset.id: PriceQuote(price_usd=Decimal("1"), source="fake", raw={}) for asset in assets if asset.id != 2}

    async def fake_evaluate(asset_id: int, quote: PriceQuote) -> bool:
        evaluated.append(asset_id)
        return True

    monkeypatch.setattr(worker.provider_registry, "provider_for", lambda name: FakeProvider())
    monkeypatch.setattr(worker, "evaluate_asset", fake_evaluate)
    client = FakeRedis()
    scheduler = worker.RefreshScheduler(client)

    await scheduler.refresh_provider("fake", [_asset(1), _asset(2), _asset(3)])

    assert batches == [[1, 2], [3]]
    assert evaluated == [1, 3]
    assert client.locked is False


@pytest.mark.asyncio
async def test_refresh_provider_skips_when_lock_is_held() -> None:
    client = FakeRedis()
    client.locked = True
    scheduler = worker.RefreshScheduler(client)

    await scheduler.refresh_provider("fake", [_asset(1)])

    assert client.locked is True
