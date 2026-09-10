from types import SimpleNamespace

import pytest

from app.bot.handlers import alerts as alert_handlers
from app.bot.messages import (
    examples_message,
    no_alerts_message,
    no_matches_message,
    provider_misconfigured_message,
    start_message,
)
from app.providers.base import ProviderConfigurationError


class FakeMessage:
    def __init__(self, *, text: str = "", user_id: int = 123) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id, first_name="Fotex", username="fotex_24")
        self.chat = SimpleNamespace(id=999)
        self.answers: list[tuple[str, object | None]] = []
        self.deleted = False

    async def answer(self, text: str, reply_markup=None, **kwargs) -> None:
        self.answers.append((text, reply_markup))
        return SimpleNamespace(chat=self.chat, message_id=len(self.answers))

    async def delete(self) -> None:
        self.deleted = True


class FakeState:
    def __init__(self, state: str | None = None, data: dict | None = None) -> None:
        self.state = state
        self.data = data or {}
        self.cleared = False

    async def get_state(self) -> str | None:
        return self.state

    async def get_data(self) -> dict:
        return self.data

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.state = state

    async def clear(self) -> None:
        self.cleared = True
        self.state = None


@pytest.mark.asyncio
async def test_cancel_alert_wizard_clears_state() -> None:
    message = FakeMessage()
    state = FakeState("AlertWizard:waiting_query")

    await alert_handlers.cancel_alert_wizard(message, state)

    assert state.cleared is True
    assert message.answers[0][0] == start_message("Fotex", "fotex_24")


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


@pytest.mark.asyncio
async def test_examples_command_replaces_previous_message(monkeypatch: pytest.MonkeyPatch) -> None:
    message = FakeMessage(text="/examples")

    async def fake_ensure_access(message, session) -> bool:
        return True

    monkeypatch.setattr(alert_handlers, "ensure_access", fake_ensure_access)

    await alert_handlers.examples_command(message, object())

    assert message.deleted is True
    assert message.answers[0][0] == examples_message()
    assert message.answers[0][1] is None
    assert message.answers[1][0] == start_message("Fotex", "fotex_24")
    assert message.answers[1][1].inline_keyboard[0][0].callback_data == "menu:newalert"


@pytest.mark.asyncio
async def test_wizard_query_uses_selected_nft_asset_type(monkeypatch: pytest.MonkeyPatch) -> None:
    message = FakeMessage(text="milady")
    state = FakeState(data={"asset_nft": True})
    calls = {}

    async def fake_ensure_access(message, session) -> bool:
        return True

    async def fake_search_assets(query: str, *, nft: bool) -> list:
        calls["query"] = query
        calls["nft"] = nft
        return []

    monkeypatch.setattr(alert_handlers, "ensure_access", fake_ensure_access)
    monkeypatch.setattr(alert_handlers.provider_registry, "search_assets", fake_search_assets)

    await alert_handlers.wizard_query(message, state, object())

    assert calls == {"query": "milady", "nft": True}
    assert message.answers[0][0] == no_matches_message(nft=True)
    assert message.answers[0][1].inline_keyboard[0][0].callback_data == "wizard:back"
    assert state.data["wizard_chat_id"] == 999
    assert state.data["wizard_message_id"] == 1


@pytest.mark.asyncio
async def test_wizard_query_reports_misconfigured_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    message = FakeMessage(text="milady")
    state = FakeState(data={"asset_nft": True})

    async def fake_ensure_access(message, session) -> bool:
        return True

    async def fake_search_assets(query: str, *, nft: bool) -> list:
        raise ProviderConfigurationError("expired")

    monkeypatch.setattr(alert_handlers, "ensure_access", fake_ensure_access)
    monkeypatch.setattr(alert_handlers.provider_registry, "search_assets", fake_search_assets)

    await alert_handlers.wizard_query(message, state, object())

    assert message.answers[0][0] == provider_misconfigured_message(nft=True)


class FakeCallback:
    def __init__(self, data: str, message: "FakeEditableMessage") -> None:
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=123, first_name="Fotex", username="fotex_24")
        self.answered = False

    async def answer(self, *args, **kwargs) -> None:
        self.answered = True


class FakeEditableMessage(FakeMessage):
    def __init__(self) -> None:
        super().__init__()
        self.message_id = 55
        self.edits: list[tuple[str, object | None]] = []

    async def edit_text(self, text: str, reply_markup=None, **kwargs) -> None:
        self.edits.append((text, reply_markup))

    async def edit_reply_markup(self, reply_markup=None) -> None:
        self.edits.append(("", reply_markup))


@pytest.mark.asyncio
async def test_wizard_back_returns_to_previous_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alert_handlers, "Message", FakeEditableMessage)
    message = FakeEditableMessage()
    state = FakeState("AlertWizard:waiting_threshold", data={"alert_type": "above", "candidates": []})

    await alert_handlers.wizard_back_to_type(FakeCallback("wizard:back", message), state)
    assert state.state == alert_handlers.AlertWizard.waiting_type
    assert message.edits[-1][0] == alert_handlers.ALERT_TYPE_PROMPT

    await alert_handlers.wizard_back_to_candidates(FakeCallback("wizard:back", message), state)
    assert state.state == alert_handlers.AlertWizard.waiting_asset
    assert message.edits[-1][0] == alert_handlers.CANDIDATES_PROMPT

    await alert_handlers.wizard_back_to_query(FakeCallback("wizard:back", message), state)
    assert state.state == alert_handlers.AlertWizard.waiting_query
    assert message.edits[-1][1].inline_keyboard[0][0].callback_data == "wizard:back"

    await alert_handlers.wizard_back_to_asset_type(FakeCallback("wizard:back", message), state)
    assert state.state == alert_handlers.AlertWizard.waiting_asset_type
    assert message.edits[-1][1].inline_keyboard[0][0].callback_data == "asset_type:token"


@pytest.mark.asyncio
async def test_wizard_back_from_shortcut_candidates_returns_to_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alert_handlers, "Message", FakeEditableMessage)
    message = FakeEditableMessage()
    state = FakeState("AlertWizard:waiting_asset", data={"parsed": {"query": "btc"}, "candidates": []})

    await alert_handlers.wizard_back_to_query(FakeCallback("wizard:back", message), state)

    assert state.cleared is True
    assert message.edits[-1][0] == start_message("Fotex", "fotex_24")


@pytest.mark.asyncio
async def test_wizard_toggle_once_flips_state_and_keyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alert_handlers, "Message", FakeEditableMessage)
    message = FakeEditableMessage()
    state = FakeState("AlertWizard:waiting_threshold", data={"alert_type": "mcap_above", "one_time": True})

    await alert_handlers.wizard_toggle_once(FakeCallback("threshold:toggle_once", message), state)

    assert state.data["one_time"] is False
    assert message.edits[-1][1].inline_keyboard[0][0].text == "One time: ❌"
    assert alert_handlers._wizard_repeat(state.data) is True
    assert alert_handlers._wizard_repeat({"alert_type": "percent"}) is None


def test_alerts_message_without_alerts_offers_only_menu() -> None:
    text, markup = alert_handlers.alerts_message([])

    assert text == no_alerts_message()
    assert [button.callback_data for row in markup.inline_keyboard for button in row] == ["wizard:cancel"]
