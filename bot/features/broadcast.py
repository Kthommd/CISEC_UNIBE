from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..i18n_es import STRINGS
from ..menus import build_back_to_menu_button
from ..utils import require_admin


@require_admin
async def show_broadcasts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = f"📢 {STRINGS.NOT_IMPLEMENTED}"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message, reply_markup=build_back_to_menu_button())
    elif update.message:
        await update.message.reply_text(message, reply_markup=build_back_to_menu_button())
