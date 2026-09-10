from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AlertWizard(StatesGroup):
    waiting_asset_type = State()
    waiting_query = State()
    waiting_asset = State()
    waiting_type = State()
    waiting_threshold = State()


class AlertEdit(StatesGroup):
    waiting_value = State()
