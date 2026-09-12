from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.db.repositories import users


@pytest.mark.asyncio
@pytest.mark.parametrize(("initial", "expected"), [("pending", "active"), ("suspended", "suspended")])
async def test_public_registration_activates_pending_users_only(monkeypatch, initial, expected):
    monkeypatch.setattr(settings, "public_access_enabled", True)
    user = SimpleNamespace(access_status=initial)
    session = SimpleNamespace(scalar=AsyncMock(return_value=1), flush=AsyncMock())
    monkeypatch.setattr(users, "get_user_by_id", AsyncMock(return_value=user))

    result = await users.upsert_telegram_user(
        session,
        telegram_id=42,
        username="birdwatcher",
        first_name="Bird",
        last_name=None,
        language_code="en",
    )

    assert result.access_status == expected
    assert session.flush.await_count == (1 if initial == "pending" else 0)
