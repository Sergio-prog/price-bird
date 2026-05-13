from types import SimpleNamespace

import pytest

from app.bot.handlers import alerts as alert_handlers


class FakeMessage:
    def __init__(self, *, text: str = "", user_id: int = 123) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None, **kwargs) -> None:
        self.answers.append((text, reply_markup))


class FakeState:
    def __init__(self, state: str | None = None) -> None:
        self.state = state
        self.cleared = False

    async def get_state(self) -> str | None:
        return self.state

    async def clear(self) -> None:
        self.cleared = True
        self.state = None


@pytest.mark.asyncio
async def test_cancel_alert_wizard_clears_state() -> None:
    message = FakeMessage()
    state = FakeState("AlertWizard:waiting_query")

    await alert_handlers.cancel_alert_wizard(message, state)

    assert state.cleared is True
    assert message.answers == [("Cancelled.", None)]


@pytest.mark.asyncio
async def test_cancel_alert_wizard_reports_when_idle() -> None:
    message = FakeMessage()
    state = FakeState()

    await alert_handlers.cancel_alert_wizard(message, state)

    assert state.cleared is False
    assert message.answers == [("Nothing to cancel.", None)]


@pytest.mark.asyncio
async def test_delete_alert_command_deletes_user_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    message = FakeMessage(text="/deletealert 42", user_id=777)
    calls = {}

    async def fake_ensure_access(message, session) -> bool:
        return True

    async def fake_delete_active_alert_for_user(session, *, telegram_id: int, alert_id: int) -> bool:
        calls["telegram_id"] = telegram_id
        calls["alert_id"] = alert_id
        return True

    class FakeSession:
        async def commit(self) -> None:
            calls["committed"] = True

    monkeypatch.setattr(alert_handlers, "ensure_access", fake_ensure_access)
    monkeypatch.setattr(alert_handlers.repo, "delete_active_alert_for_user", fake_delete_active_alert_for_user)

    await alert_handlers.delete_alert(message, FakeSession())

    assert calls == {"telegram_id": 777, "alert_id": 42, "committed": True}
    assert message.answers == [("Deleted alert #42.", None)]
