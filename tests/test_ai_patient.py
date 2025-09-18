from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from bot.features import ai_patient
from bot.features.ai_patient import (
    SESSION_KEY,
    PATIENT_PANEL_EXAM,
    PATIENT_PANEL_IMAGES,
    PATIENT_PANEL_LABS,
    PATIENT_PANELS,
    PATIENT_TERMINATE,
    _build_patient_keyboard,
    handle_patient_message,
    handle_patient_termination,
)
from bot.i18n_es import STRINGS


def test_build_patient_keyboard_layout():
    keyboard = _build_patient_keyboard()
    assert all(len(row) == 1 for row in keyboard.inline_keyboard)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    expected = [
        PATIENT_PANELS[PATIENT_PANEL_LABS],
        PATIENT_PANELS[PATIENT_PANEL_IMAGES],
        PATIENT_PANELS[PATIENT_PANEL_EXAM],
        PATIENT_PANELS[PATIENT_TERMINATE],
    ]
    assert labels == expected


@pytest.mark.parametrize("user_text", ["Hola", "Necesito tus antecedentes"])
def test_handle_patient_message_includes_disclaimer(monkeypatch, user_text):
    replies: list[str] = []

    class DummyMessage:
        def __init__(self, text: str) -> None:
            self.text = text

        async def reply_text(self, text: str, reply_markup=None) -> None:  # pragma: no cover - signature
            replies.append(text)

    async def fake_fetch(context):
        return {
            "id": 1,
            "slug": "dummy",
            "display_name": "Paciente",
            "summary": "Caso de prueba",
            "persona": {"demografia": "Paciente ficticio"},
        }

    async def fake_append(*args, **kwargs):
        return None

    async def fake_history(*args, **kwargs):
        return []

    async def fake_call_llm(payload):
        return "Respuesta breve del paciente"

    monkeypatch.setattr(ai_patient, "_fetch_patient", fake_fetch)
    monkeypatch.setattr(ai_patient, "_append_log", fake_append)
    monkeypatch.setattr(ai_patient, "_load_history", fake_history)
    monkeypatch.setattr(ai_patient, "_call_llm", fake_call_llm)

    update = SimpleNamespace(message=DummyMessage(user_text))
    context = SimpleNamespace(user_data={SESSION_KEY: 5}, application_data={})

    asyncio.run(handle_patient_message(update, context))

    assert replies, "La función debe responder al estudiante"
    assert replies[0].startswith(STRINGS.AI_DISCLAIMER)


def test_handle_patient_termination_formats_rubric(monkeypatch):
    replies: list[str] = []
    log_calls: list[tuple] = []

    class DummyMessage:
        async def reply_text(self, text: str, reply_markup=None) -> None:  # pragma: no cover - signature
            replies.append(text)

    class DummySimSession:
        def __init__(self) -> None:
            self.status = "active"
            self.rubric = None
            self.ended_at = None

    class DummyDBSession:
        def __init__(self) -> None:
            self.instance = DummySimSession()
            self.committed = False

        async def __aenter__(self):  # pragma: no cover - context manager protocol
            return self

        async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - context manager protocol
            return False

        async def get(self, model, pk):
            return self.instance

        async def commit(self):
            self.committed = True

    dummy_session = DummyDBSession()

    def fake_get_session():
        return dummy_session

    async def fake_fetch(context):
        return {
            "id": 1,
            "slug": "dummy",
            "display_name": "Paciente",
            "summary": "Caso de prueba",
            "persona": {"demografia": "Paciente ficticio"},
        }

    async def fake_history(*args, **kwargs):
        return [SimpleNamespace(role="student", message="Hola")]

    async def fake_call_llm(payload):
        return (
            '{"anamnesis":{"score":2,"feedback":"Buena exploración."},'
            '"hipotesis":{"score":1,"feedback":"Falta ampliar diagnósticos."},'
            '"examen_fisico":{"score":2,"feedback":"Exploración completa."},'
            '"uso_pruebas":{"score":1,"feedback":"Solicita estudios básicos."},'
            '"proximos_pasos":{"score":1,"feedback":"Plantea seguimiento."},'
            '"resumen":"Continúa profundizando."}'
        )

    async def fake_append(*args, **kwargs):
        log_calls.append(args)

    monkeypatch.setattr(ai_patient, "get_session", fake_get_session)
    monkeypatch.setattr(ai_patient, "_fetch_patient", fake_fetch)
    monkeypatch.setattr(ai_patient, "_load_history", fake_history)
    monkeypatch.setattr(ai_patient, "_call_llm", fake_call_llm)
    monkeypatch.setattr(ai_patient, "_append_log", fake_append)

    update = SimpleNamespace(message=DummyMessage(), callback_query=None)
    context = SimpleNamespace(user_data={SESSION_KEY: 7}, application_data={})

    asyncio.run(handle_patient_termination(update, context))

    assert replies and replies[0].startswith(STRINGS.PATIENT_EVAL_HEADER)
    assert dummy_session.instance.status == "completed"
    assert dummy_session.committed is True
    assert context.user_data.get(SESSION_KEY) is None
    assert dummy_session.instance.rubric is not None
    parsed = dummy_session.instance.rubric["parsed"]
    assert parsed["dimensions"]["anamnesis"]["score"] == 2
    assert log_calls, "Se debe registrar la evaluación en los logs"
