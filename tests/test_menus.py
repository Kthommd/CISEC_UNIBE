from __future__ import annotations

from bot.menus import build_main_menu, build_start_message


def test_build_start_message_includes_name():
    text = build_start_message("Ana")
    assert "Ana" in text


def test_main_menu_has_single_button_rows():
    markup = build_main_menu()
    assert all(len(row) == 1 for row in markup.inline_keyboard)
