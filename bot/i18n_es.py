from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class MenuOption:
    text: str
    callback_data: str


class SpanishStrings:
    BOT_NAME = "CISEC Nexus"
    START_GREETING = (
        "👋 ¡Hola {name}! Soy CISEC Nexus, tu compañera académica. "
        "Desde aquí encontrarás simulaciones clínicas, banco IFOM y recursos oficiales."
    )
    MAIN_MENU_OPTIONS: List[MenuOption] = [
        MenuOption(text="📅 Semana académica", callback_data="MENU_WEEK"),
        MenuOption(text="📚 Sílabo y calificaciones", callback_data="MENU_SYLLABUS"),
        MenuOption(text="🧪 Simulador IFOM", callback_data="MENU_IFOM"),
        MenuOption(text="🩺 Paciente simulado", callback_data="MENU_PATIENT"),
        MenuOption(text="📢 Novedades y avisos", callback_data="MENU_BROADCASTS"),
    ]
    NOT_IMPLEMENTED = "🚧 Función en construcción."
    ONLY_ADMINS = "Esta opción es solo para administradores."
    START_BUTTON_LABEL = "Menú principal"

    PATIENT_GUIDE = (
        "Puedes conversar libremente conmigo como paciente simulado. "
        "Pregunta por antecedentes, hábitos, domicilio, síntomas o lo que necesites para tu anamnesis."
    )
    AI_DISCLAIMER = (
        "⚠️ Simulación educativa: la información proviene de notas académicas ficticias. "
        "No constituye diagnóstico ni tratamiento real."
    )
    PATIENT_NOT_FOUND = "No se encontró el caso clínico disponible en este momento."
    PATIENT_NO_ACTIVE_SESSION = (
        "No hay una simulación activa. Vuelve al menú principal e inicia el caso para continuar."
    )
    PATIENT_PANEL_LABELS: Dict[str, str] = {
        "labs": "Laboratorios",
        "images": "Imágenes",
        "exam": "Examen físico",
        "end": "Terminar caso",
    }
    PATIENT_PANEL_EMPTY = "Sin información registrada."
    PATIENT_PANEL_LABS_EMPTY = "Sin datos de laboratorio disponibles."
    PATIENT_PANEL_IMAGES_EMPTY = "Sin estudios de imagen disponibles."
    PATIENT_PANEL_EXAM_EMPTY = "Sin examen físico registrado."

    PATIENT_EVAL_HEADER = "📊 Evaluación formativa (0–2 por dimensión)"
    PATIENT_EVAL_SUMMARY_PREFIX = "Síntesis:"
    PATIENT_EVAL_REMINDER = (
        "Continúa profundizando tus hipótesis y planes sin adelantar diagnósticos ni tratamientos definitivos."
    )
    PATIENT_EVAL_FALLBACK = "No fue posible generar la retroalimentación en este momento."
    PATIENT_EVAL_EMPTY_FEEDBACK = "Sin observaciones registradas."
    PATIENT_EVAL_DIMENSIONS: Tuple[Tuple[str, str], ...] = (
        ("anamnesis", "Anamnesis"),
        ("hipotesis", "Hipótesis"),
        ("examen_fisico", "Examen físico"),
        ("uso_pruebas", "Uso de pruebas"),
        ("proximos_pasos", "Próximos pasos"),
    )


STRINGS = SpanishStrings()
