from __future__ import annotations

import logging
from typing import Awaitable, Callable, Dict

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PollAnswerHandler,
    filters,
)

from common.config import settings

from .features.ai_patient import (
    handle_patient_callback,
    handle_patient_message,
    handle_patient_sim,
)
from .features.broadcast import show_broadcasts
from .features.ifom import handle_ifom, handle_ifom_poll_answer
from .features.syllabus_grades import (
    DOCUMENT_CALLBACK_PREFIX,
    handle_document_callback,
    handle_document_upload,
    handle_syllabus,
)
from .features.week import show_week_status
from .i18n_es import STRINGS
from .menus import build_main_menu, build_start_message

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    first_name = update.effective_user.first_name if update.effective_user else None
    text = build_start_message(first_name)
    if update.message:
        await update.message.reply_text(text, reply_markup=build_main_menu())
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=build_main_menu())


CALLBACK_HANDLERS: Dict[str, Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]] = {
    "MENU_WEEK": show_week_status,
    "MENU_SYLLABUS": handle_syllabus,
    "MENU_IFOM": handle_ifom,
    "MENU_PATIENT": handle_patient_sim,
    "MENU_BROADCASTS": show_broadcasts,
    "MENU_MAIN": start,
}


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    if query.data and query.data.startswith(DOCUMENT_CALLBACK_PREFIX):
        await handle_document_callback(update, context, query.data)
        return
    if query.data and query.data.startswith("PATIENT_"):
        await handle_patient_callback(update, context, query.data)
        return
    action = CALLBACK_HANDLERS.get(query.data)
    if not action:
        await query.answer()
        return
    await action(update, context)


def build_application() -> Application:
    logging.basicConfig(level=getattr(logging, settings.bot_log_level.upper(), logging.INFO))
    application = ApplicationBuilder().token(settings.telegram_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_document_upload))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient_message))
    application.add_handler(CallbackQueryHandler(handle_menu_callback, pattern=r"^(MENU_|DOC_|PATIENT_)"))
    application.add_handler(PollAnswerHandler(handle_ifom_poll_answer))
    return application


def main() -> None:
    application = build_application()
    logger.info("Iniciando bot %s", STRINGS.BOT_NAME)
    application.run_polling()


if __name__ == "__main__":
    main()
