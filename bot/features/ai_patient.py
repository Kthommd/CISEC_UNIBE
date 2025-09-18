from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from common.config import settings
from common.db import Patient, SimLog, SimSession, get_session

from ..i18n_es import STRINGS
from ..menus import build_back_to_menu_button

PATIENT_PANEL_LABS = "PATIENT_LABS"
PATIENT_PANEL_IMAGES = "PATIENT_IMAGES"
PATIENT_PANEL_EXAM = "PATIENT_EXAM"
PATIENT_TERMINATE = "PATIENT_END"

PATIENT_PANELS = {
    PATIENT_PANEL_LABS: STRINGS.PATIENT_PANEL_LABELS["labs"],
    PATIENT_PANEL_IMAGES: STRINGS.PATIENT_PANEL_LABELS["images"],
    PATIENT_PANEL_EXAM: STRINGS.PATIENT_PANEL_LABELS["exam"],
    PATIENT_TERMINATE: STRINGS.PATIENT_PANEL_LABELS["end"],
}

SESSION_KEY = "patient_session_id"
PATIENT_CACHE_KEY = "patient_cache"
MAX_HISTORY_MESSAGES = 12
RUBRIC_DIMENSIONS = STRINGS.PATIENT_EVAL_DIMENSIONS


def _build_patient_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(PATIENT_PANELS[PATIENT_PANEL_LABS], callback_data=PATIENT_PANEL_LABS)],
        [InlineKeyboardButton(PATIENT_PANELS[PATIENT_PANEL_IMAGES], callback_data=PATIENT_PANEL_IMAGES)],
        [InlineKeyboardButton(PATIENT_PANELS[PATIENT_PANEL_EXAM], callback_data=PATIENT_PANEL_EXAM)],
        [InlineKeyboardButton(PATIENT_PANELS[PATIENT_TERMINATE], callback_data=PATIENT_TERMINATE)],
    ]
    return InlineKeyboardMarkup(rows)


async def _fetch_patient(context: ContextTypes.DEFAULT_TYPE) -> Optional[Dict[str, object]]:
    cache: Dict[str, Dict[str, object]] = context.application_data.setdefault(PATIENT_CACHE_KEY, {})
    slug = settings.default_patient_slug
    if slug in cache:
        return cache[slug]

    async with get_session() as session:
        patient = await session.scalar(select(Patient).where(Patient.slug == slug))
        if not patient:
            return None
        data = {
            "id": patient.id,
            "slug": patient.slug,
            "display_name": patient.display_name,
            "summary": patient.summary or "Caso clínico en simulación.",
            "persona": patient.persona or {},
        }
        cache[slug] = data
        return data


async def _get_or_create_session(user_id: int, patient_id: int) -> SimSession:
    async with get_session() as session:
        existing = await session.scalar(
            select(SimSession)
            .where(
                SimSession.user_id == user_id,
                SimSession.patient_id == patient_id,
                SimSession.status.in_(("active", "activa")),
            )
            .order_by(SimSession.started_at.desc())
        )
        if existing:
            return existing
        sim_session = SimSession(user_id=user_id, patient_id=patient_id, status="active")
        session.add(sim_session)
        await session.commit()
        await session.refresh(sim_session)
        return sim_session


async def _append_log(session_id: int, role: str, message: str, metadata: Optional[Dict[str, object]] = None) -> None:
    async with get_session() as session:
        log = SimLog(session_id=session_id, role=role, message=message, extra=metadata or {})
        session.add(log)
        await session.commit()


async def _load_history(session_id: int) -> List[SimLog]:
    async with get_session() as session:
        result = await session.scalars(
            select(SimLog).where(SimLog.session_id == session_id).order_by(SimLog.created_at.asc())
        )
        logs = result.all()
        return logs[-MAX_HISTORY_MESSAGES:]


def _history_to_messages(logs: List[SimLog]) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    for entry in logs:
        if entry.role not in {"student", "patient"}:
            continue
        role = "user" if entry.role == "student" else "assistant"
        messages.append({"role": role, "content": entry.message})
    return messages


async def _call_llm(payload: Dict[str, object]) -> str:
    async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
        response = await client.post(f"{settings.api_base_url}/llm/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("reply", "Lo siento, no pude generar una respuesta en este momento.")


def _build_system_prompt(persona: Dict[str, object]) -> str:
    demographics = persona.get("demografia") or "Paciente sin datos demográficos específicos."
    antecedentes = persona.get("antecedentes") or "Sin antecedentes registrados."
    motivo = persona.get("motivo_consulta") or "Sin motivo de consulta declarado."
    narrative = persona.get("narrativa") or ""
    instructions = (
        "Actúa como el paciente descrito en la historia clínica. "
        "Responde en primera persona, con tono empático y coherente, siempre en español neutro. "
        "Fundamenta tus respuestas únicamente en la información proporcionada; si algo no está documentado, admite desconocimiento o neutralidad. "
        "Nunca reveles diagnósticos ni tratamientos ni sugieras decisiones médicas finales."
    )
    return (
        f"{instructions}\n\n"
        f"Demografía: {demographics}\n"
        f"Motivo de consulta: {motivo}\n"
        f"Antecedentes: {antecedentes}\n"
        f"Narrativa adicional: {narrative}"
    )


def _extract_json_payload(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        segments = [segment.strip() for segment in text.split("```") if segment.strip()]
        for segment in segments:
            if segment.lower().startswith("json"):
                return segment[4:].strip()
            return segment
    return text


def _format_evaluation(raw: str) -> tuple[str, Dict[str, object]]:
    parsed_payload: Dict[str, object] = {}
    try:
        clean = _extract_json_payload(raw)
        loaded = json.loads(clean)
        if isinstance(loaded, dict):
            parsed_payload = loaded
    except json.JSONDecodeError:
        parsed_payload = {}

    if not parsed_payload:
        fallback_text = raw.strip() or STRINGS.PATIENT_EVAL_FALLBACK
        text = f"{STRINGS.PATIENT_EVAL_HEADER}\n\n{fallback_text}\n\n{STRINGS.PATIENT_EVAL_REMINDER}"
        return text, {"error": "unparsed"}

    lines = [STRINGS.PATIENT_EVAL_HEADER]
    dimensions_payload: Dict[str, Dict[str, object]] = {}
    for key, label in RUBRIC_DIMENSIONS:
        entry = parsed_payload.get(key) if isinstance(parsed_payload.get(key), dict) else {}
        score = entry.get("score") if isinstance(entry, dict) else None
        if not isinstance(score, (int, float)):
            score = 0
        score_int = int(max(0, min(2, score)))
        feedback = entry.get("feedback") if isinstance(entry, dict) else None
        if not isinstance(feedback, str) or not feedback.strip():
            feedback = STRINGS.PATIENT_EVAL_EMPTY_FEEDBACK
        feedback = feedback.strip()
        dimensions_payload[key] = {"score": score_int, "feedback": feedback}
        lines.append(f"• {label}: {score_int}/2 — {feedback}")

    summary = parsed_payload.get("resumen") or parsed_payload.get("summary")
    summary_text = summary.strip() if isinstance(summary, str) else ""
    if summary_text:
        lines.append("")
        lines.append(f"{STRINGS.PATIENT_EVAL_SUMMARY_PREFIX} {summary_text}")

    lines.append("")
    lines.append(STRINGS.PATIENT_EVAL_REMINDER)

    formatted = "\n".join(lines)
    rubric_payload = {"dimensions": dimensions_payload, "summary": summary_text}
    return formatted, rubric_payload


async def handle_patient_sim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    patient = await _fetch_patient(context)
    if not patient:
        message = STRINGS.PATIENT_NOT_FOUND
        if update.callback_query:
            await update.callback_query.answer(message, show_alert=True)
        elif update.message:
            await update.message.reply_text(message)
        return

    sim_session = await _get_or_create_session(user.id, int(patient["id"]))
    context.user_data[SESSION_KEY] = sim_session.id
    context.user_data["patient_slug"] = patient["slug"]

    intro_lines = [
        f"🩺 Caso simulado: {patient['display_name']}",
        patient["summary"],
        "",
        STRINGS.PATIENT_GUIDE,
    ]
    text = "\n".join(intro_lines)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=_build_patient_keyboard())
    elif update.message:
        await update.message.reply_text(text, reply_markup=_build_patient_keyboard())

    await _append_log(sim_session.id, "system", "Sesión iniciada")


async def _handle_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, panel: str) -> None:
    session_id = context.user_data.get(SESSION_KEY)
    patient = await _fetch_patient(context)
    if not session_id or not patient:
        if update.callback_query:
            await update.callback_query.answer(STRINGS.PATIENT_NO_ACTIVE_SESSION, show_alert=True)
        return
    persona = patient["persona"]
    content_map = {
        PATIENT_PANEL_LABS: persona.get("laboratorios") or STRINGS.PATIENT_PANEL_LABS_EMPTY,
        PATIENT_PANEL_IMAGES: persona.get("imagenes") or STRINGS.PATIENT_PANEL_IMAGES_EMPTY,
        PATIENT_PANEL_EXAM: persona.get("examen_fisico") or STRINGS.PATIENT_PANEL_EXAM_EMPTY,
    }
    text = content_map.get(panel, STRINGS.PATIENT_PANEL_EMPTY)
    if not text:
        text = STRINGS.PATIENT_PANEL_EMPTY

    await _append_log(session_id, "panel", f"{panel}:{text[:60]}")
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=_build_patient_keyboard())


async def handle_patient_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, panel: str) -> None:
    if panel == PATIENT_TERMINATE:
        await handle_patient_termination(update, context)
    else:
        await _handle_panel(update, context, panel)


async def handle_patient_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or update.message.text is None:
        return
    session_id = context.user_data.get(SESSION_KEY)
    patient = await _fetch_patient(context)
    if not session_id or not patient:
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    await _append_log(session_id, "student", user_text)
    history = await _load_history(session_id)
    messages = _history_to_messages(history)
    system_prompt = _build_system_prompt(patient["persona"])

    payload = {
        "persona": patient["persona"],
        "system": system_prompt,
        "messages": messages + [{"role": "user", "content": user_text}],
        "temperature": settings.ollama_temperature,
        "max_tokens": settings.ollama_max_tokens,
    }

    try:
        reply = await _call_llm(payload)
    except httpx.HTTPError:
        reply = "Estoy un poco confundida, ¿podrías repetir la pregunta?"

    await _append_log(session_id, "patient", reply)
    await update.message.reply_text(f"{STRINGS.AI_DISCLAIMER}\n\n{reply}")


async def handle_patient_termination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session_id = context.user_data.get(SESSION_KEY)
    patient = await _fetch_patient(context)
    if not session_id or not patient:
        if update.callback_query:
            await update.callback_query.answer(STRINGS.PATIENT_NO_ACTIVE_SESSION, show_alert=True)
        return

    history = await _load_history(session_id)
    evaluation_prompt = (
        "Eres tutora clínica. Evalúa la interacción según la conversación previa. "
        "Para cada dimensión (anamnesis, hipótesis, examen físico, uso de pruebas, próximos pasos) "
        "asigna una puntuación entre 0 y 2 y proporciona una retroalimentación breve. "
        "Devuelve únicamente un objeto JSON sin formato Markdown con la siguiente estructura: "
        "{\"anamnesis\":{\"score\":0-2,\"feedback\":\"...\"},"
        "\"hipotesis\":{...},\"examen_fisico\":{...},\"uso_pruebas\":{...},\"proximos_pasos\":{...},"
        "\"resumen\":\"comentario final sin diagnóstico ni tratamiento\"}. "
        "No repitas instrucciones y responde siempre en español neutro."
    )
    messages = _history_to_messages(history)
    payload = {
        "persona": patient["persona"],
        "system": evaluation_prompt,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 400,
    }

    try:
        evaluation = await _call_llm(payload)
    except httpx.HTTPError:
        evaluation = STRINGS.PATIENT_EVAL_FALLBACK

    formatted_text, rubric_payload = _format_evaluation(evaluation)

    async with get_session() as session:
        sim_session = await session.get(SimSession, session_id)
        if sim_session:
            sim_session.status = "completed"
            sim_session.rubric = {
                "raw": evaluation,
                "parsed": rubric_payload,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            sim_session.ended_at = datetime.now(timezone.utc)
            await session.commit()

    await _append_log(session_id, "system", f"evaluacion:{formatted_text[:120]}")
    context.user_data.pop(SESSION_KEY, None)
    context.user_data.pop("patient_slug", None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            formatted_text, reply_markup=build_back_to_menu_button()
        )
    else:
        await update.message.reply_text(
            formatted_text, reply_markup=build_back_to_menu_button()
        )


async def handle_patient_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    if data in PATIENT_PANELS:
        await handle_patient_panel(update, context, data)
