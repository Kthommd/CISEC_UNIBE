from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from telegram import Update
from telegram.ext import ContextTypes

from common.config import settings

from ..menus import build_back_to_menu_button


@dataclass
class WeekStatus:
    label: str
    progress_bar: str
    percentage: float
    current_week: int | None


def compute_week_status(current_date: date) -> WeekStatus:
    start = date.fromisoformat(settings.period_start)
    end = date.fromisoformat(settings.period_end)
    total_weeks = settings.total_weeks

    if current_date < start:
        days_left = (start - current_date).days
        label = f"📅 El ciclo inicia el {start.strftime('%d/%m/%Y')} (faltan {days_left} días)."
        return WeekStatus(label=label, progress_bar="░" * 10, percentage=0.0, current_week=None)

    if current_date > end:
        label = f"✅ El ciclo finalizó el {end.strftime('%d/%m/%Y')}"
        return WeekStatus(label=label, progress_bar="▓" * 10, percentage=100.0, current_week=total_weeks)

    days_total = (end - start).days + 1
    days_elapsed = (current_date - start).days
    progress = max(0.0, min(1.0, days_elapsed / days_total))
    week_index = min(total_weeks, days_elapsed // 7 + 1)

    segments = 10
    filled = max(0, min(segments, round(progress * segments)))
    bar = "▓" * filled + "░" * (segments - filled)
    percentage = round(progress * 100, 1)
    label = (
        f"Semana {week_index} de {total_weeks}\n"
        f"Progreso: {bar} {percentage}%\n"
        f"{start.strftime('%d/%m/%Y')} → {end.strftime('%d/%m/%Y')}"
    )
    return WeekStatus(label=label, progress_bar=bar, percentage=percentage, current_week=week_index)


async def show_week_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current = datetime.now().date()
    status = compute_week_status(current)
    text = status.label

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=build_back_to_menu_button())
    elif update.message:
        await update.message.reply_text(text, reply_markup=build_back_to_menu_button())
