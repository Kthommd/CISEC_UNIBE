from __future__ import annotations

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .i18n_es import STRINGS


def build_start_message(first_name: Optional[str]) -> str:
    name = first_name or "estudiante"
    return STRINGS.START_GREETING.format(name=name)


def build_main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(option.text, callback_data=option.callback_data)]
        for option in STRINGS.MAIN_MENU_OPTIONS
    ]
    return InlineKeyboardMarkup(keyboard)


def build_back_to_menu_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(STRINGS.START_BUTTON_LABEL, callback_data="MENU_MAIN")]]
    )
