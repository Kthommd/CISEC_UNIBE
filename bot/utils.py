from __future__ import annotations

from functools import wraps
from typing import Awaitable, Callable, TypeVar

from telegram import Update
from telegram.ext import ContextTypes

from common.config import settings

from .i18n_es import STRINGS

THandler = TypeVar("THandler", bound=Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]])


def is_admin(user_id: int | None) -> bool:
    if user_id is None:
        return False
    return user_id in settings.admin_ids


def require_admin(handler: THandler) -> THandler:
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # type: ignore[misc]
        user = update.effective_user
        if not is_admin(user.id if user else None):
            if update.callback_query:
                await update.callback_query.answer(STRINGS.ONLY_ADMINS, show_alert=True)
                return
            message = update.effective_message
            if message:
                await message.reply_text(STRINGS.ONLY_ADMINS)
            return
        await handler(update, context)

    return wrapper  # type: ignore[return-value]
