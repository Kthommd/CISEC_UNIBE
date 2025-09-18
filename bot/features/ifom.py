from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Poll, Update
from telegram.ext import ContextTypes

from common.db import IFOMAttempt, IFOMItem, get_session

from ..i18n_es import STRINGS

POLL_STORE_KEY = "ifom_polls"
LETTERS = ["A", "B", "C", "D", "E"]


def _poll_store(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Dict[str, object]]:
    return context.application_data.setdefault(POLL_STORE_KEY, {})


def _build_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔁 Otra pregunta", callback_data="MENU_IFOM")],
            [InlineKeyboardButton(STRINGS.START_BUTTON_LABEL, callback_data="MENU_MAIN")],
        ]
    )


async def handle_ifom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    async with get_session() as session:
        statement = select(IFOMItem).order_by(func.random()).limit(1)
        item = await session.scalar(statement)

    if not item:
        message = "⚠️ Aún no hay preguntas cargadas en el banco IFOM."
        if update.callback_query:
            await update.callback_query.answer(message, show_alert=True)
        elif update.message:
            await update.message.reply_text(message)
        return

    if update.callback_query:
        await update.callback_query.answer("Pregunta enviada a tu chat.")
    elif update.message:
        await update.message.reply_text("🧪 Prepárate, nueva pregunta IFOM en camino.")

    poll_message = await context.bot.send_poll(
        chat_id=chat.id,
        question=item.stem,
        options=item.options,
        type=Poll.QUIZ,
        correct_option_id=item.answer_index,
        is_anonymous=False,
    )

    _poll_store(context)[poll_message.poll.id] = {
        "item_id": item.id,
        "user_id": user.id,
        "chat_id": chat.id,
        "message_id": poll_message.message_id,
        "started_at": datetime.utcnow().timestamp(),
    }


async def _persist_attempt(
    item: IFOMItem,
    user_id: int,
    selected_index: Optional[int],
    elapsed_seconds: Optional[int],
    is_correct: bool,
) -> None:
    async with get_session() as session:
        attempt = IFOMAttempt(
            user_id=user_id,
            item_id=item.id,
            chosen_index=selected_index if selected_index is not None else -1,
            is_correct=is_correct,
            response_time_seconds=elapsed_seconds,
        )
        session.add(attempt)
        await session.commit()


async def handle_ifom_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    answer = update.poll_answer
    if not answer:
        return

    data = _poll_store(context).pop(answer.poll_id, None)
    if not data:
        return

    item_id = data.get("item_id")
    chat_id = data.get("chat_id")
    message_id = data.get("message_id")
    user_id = data.get("user_id")
    started_at = data.get("started_at")

    if chat_id is None or user_id is None:
        return

    async with get_session() as session:
        item = await session.get(IFOMItem, item_id)

    if not item:
        return

    selected_indices = answer.option_ids or []
    selected_index = selected_indices[0] if selected_indices else None
    is_correct = selected_index == item.answer_index
    elapsed = None
    if isinstance(started_at, (int, float)):
        elapsed = max(0, int(datetime.utcnow().timestamp() - started_at))

    await _persist_attempt(item, user_id, selected_index, elapsed, is_correct)

    if chat_id and message_id:
        try:
            await context.bot.stop_poll(chat_id, message_id)
        except Exception:
            pass

    correct_letter = LETTERS[item.answer_index] if item.answer_index < len(LETTERS) else str(item.answer_index + 1)
    correct_text = item.options[item.answer_index]
    if selected_index is None:
        verdict = "⏱️ Tiempo agotado o sin respuesta."
    elif is_correct:
        verdict = "✅ ¡Respuesta correcta!"
    else:
        verdict = "❌ Respuesta incorrecta."

    explanation_lines = [verdict, f"Respuesta correcta: {correct_letter}. {correct_text}"]
    if item.explanation:
        explanation_lines.append("")
        explanation_lines.append(f"Explicación: {item.explanation}")
    if item.tags:
        explanation_lines.append("")
        explanation_lines.append("Etiquetas: " + ", ".join(item.tags))

    await context.bot.send_message(chat_id=chat_id, text="\n".join(explanation_lines), reply_markup=_build_result_keyboard())
