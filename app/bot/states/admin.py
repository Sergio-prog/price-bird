from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Broadcast(StatesGroup):
    audience = State()
    recipients = State()
    content = State()
    confirm = State()
    button_text = State()
    button_action = State()
