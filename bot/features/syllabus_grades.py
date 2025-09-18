from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from common.config import settings
from common.db import Document, get_session

from ..i18n_es import STRINGS
from ..menus import build_back_to_menu_button
from ..utils import require_admin

DOCUMENT_CALLBACK_PREFIX = "DOC_"


def _build_documents_keyboard(documents: List[Document]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"📄 {doc.title}", callback_data=f"{DOCUMENT_CALLBACK_PREFIX}{doc.id}")]
        for doc in documents
    ]
    rows.append([InlineKeyboardButton(STRINGS.START_BUTTON_LABEL, callback_data="MENU_MAIN")])
    return InlineKeyboardMarkup(rows)


async def handle_syllabus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with get_session() as session:
        result = await session.scalars(select(Document).order_by(Document.uploaded_at.desc()))
        documents = result.all()

    if documents:
        lines = ["📚 Recursos académicos disponibles:"]
        for index, doc in enumerate(documents, start=1):
            lines.append(f"{index}. {doc.title}")
        text = "\n".join(lines)
        markup = _build_documents_keyboard(documents)
    else:
        text = "📚 Aún no hay documentos publicados. Pide a tu docente que suba el primer PDF."
        markup = build_back_to_menu_button()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    elif update.message:
        await update.message.reply_text(text, reply_markup=markup)


@require_admin
async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.document:
        return
    document = update.message.document
    if document.mime_type != "application/pdf":
        await update.message.reply_text("Solo se permiten archivos PDF en esta sección.")
        return

    directory = Path(settings.syllabus_dir)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = document.file_name or f"documento_{timestamp}.pdf"
    path = directory / f"{timestamp}_{document.file_unique_id}.pdf"

    file = await context.bot.get_file(document.file_id)
    await file.download_to_drive(custom_path=str(path))

    async with get_session() as session:
        record = Document(
            title=filename,
            file_path=str(path),
            file_type="pdf",
            uploaded_by=update.effective_user.id if update.effective_user else 0,
            extra={
                "telegram_file_id": document.file_id,
                "file_unique_id": document.file_unique_id,
                "original_name": filename,
            },
        )
        session.add(record)
        await session.commit()

    await update.message.reply_text(f"📄 '{filename}' cargado correctamente y disponible para los estudiantes.")


async def handle_document_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str) -> None:
    query = update.callback_query
    if not query:
        return

    try:
        document_id = int(payload.replace(DOCUMENT_CALLBACK_PREFIX, ""))
    except ValueError:
        await query.answer("Documento no válido", show_alert=True)
        return

    async with get_session() as session:
        document = await session.get(Document, document_id)

    if not document:
        await query.answer("Documento no encontrado", show_alert=True)
        return

    path = Path(document.file_path)
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return

    await query.answer("Enviando documento…")
    if path.exists():
        with path.open("rb") as file_handle:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file_handle,
                filename=path.name,
                caption=document.title,
            )
    elif document.extra and document.extra.get("telegram_file_id"):
        await context.bot.send_document(
            chat_id=chat_id,
            document=document.extra["telegram_file_id"],
            caption=document.title,
        )
    else:
        await context.bot.send_message(chat_id=chat_id, text="El archivo no está disponible en el servidor.")
