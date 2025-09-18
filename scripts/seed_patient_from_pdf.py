from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from PyPDF2 import PdfReader
from sqlalchemy import select

from common.config import settings
from common.db import Patient, init_db, get_session


SECTION_ALIASES = {
    "demografia": ["datos generales", "demografía", "identificación"],
    "motivo_consulta": ["motivo de consulta", "consulta"],
    "antecedentes": ["antecedentes", "historia", "hx"],
    "medicamentos": ["medicamentos", "tratamiento actual"],
    "alergias": ["alergias"],
    "habitos": ["hábitos", "social"],
    "vitales": ["signos vitales", "vitales"],
    "examen_fisico": ["examen físico", "ef"],
    "laboratorios": ["laboratorio", "lab", "labs"],
    "imagenes": ["imagen", "imágenes", "estudios de imagen"],
    "impresion": ["impresión diagnóstica", "discusión"],
    "narrativa": ["narrativa", "resumen narrativo"],
}


@dataclass
class Persona:
    slug: str
    display_name: str
    summary: str
    persona: Dict[str, str]
    notes_path: str


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    return path.read_text(encoding="utf-8")


def detect_section(line: str) -> Optional[str]:
    lower = line.lower().strip(": ")
    for key, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            if lower.startswith(alias):
                return key
    return None


def parse_sections(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current = "narrativa"
    sections[current] = []

    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if not line:
            continue
        section = detect_section(line)
        if section:
            current = section
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    return sections


def build_persona(slug: str, path: Path, sections: Dict[str, List[str]]) -> Persona:
    display_name = next(iter(sections.get("demografia", [slug.replace("-", " ").title()])), "Paciente")
    resumen = " ".join(sections.get("motivo_consulta", [])) or "Caso clínico para práctica de anamnesis."

    persona = {
        "demografia": "\n".join(sections.get("demografia", [])) or "Estudiante recibe paciente sin datos identificatorios."
    }
    persona["motivo_consulta"] = "\n".join(sections.get("motivo_consulta", []))
    persona["antecedentes"] = "\n".join(sections.get("antecedentes", []))
    persona["medicamentos"] = "\n".join(sections.get("medicamentos", []))
    persona["alergias"] = "\n".join(sections.get("alergias", []))
    persona["habitos"] = "\n".join(sections.get("habitos", []))
    persona["vitales"] = "\n".join(sections.get("vitales", []))
    persona["examen_fisico"] = "\n".join(sections.get("examen_fisico", []))
    persona["laboratorios"] = "\n".join(sections.get("laboratorios", []))
    persona["imagenes"] = "\n".join(sections.get("imagenes", []))
    persona["impresion"] = "\n".join(sections.get("impresion", []))
    persona["narrativa"] = "\n".join(sections.get("narrativa", []))

    return Persona(
        slug=slug,
        display_name=display_name,
        summary=resumen,
        persona=persona,
        notes_path=str(path),
    )


async def persist_persona(persona: Persona) -> None:
    await init_db()
    async with get_session() as session:
        stmt = select(Patient).where(Patient.slug == persona.slug)
        existing = await session.scalar(stmt)
        payload = {
            "slug": persona.slug,
            "display_name": persona.display_name,
            "summary": persona.summary,
            "persona": persona.persona,
            "notes_path": persona.notes_path,
        }
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            session.add(Patient(**payload))
        await session.commit()
    print(f"Paciente '{persona.slug}' actualizado")


async def main(path: Path, slug: Optional[str] = None) -> None:
    text = extract_text(path)
    if not text:
        raise ValueError("No se pudo extraer texto del archivo")
    sections = parse_sections(text)
    patient_slug = slug or path.stem.replace(" ", "-").lower()
    persona = build_persona(patient_slug, path, sections)
    await persist_persona(persona)

    output_json = Path(settings.data_dir) / f"{persona.slug}.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persona.persona, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Persona guardada en {output_json}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed de paciente desde PDF/TXT")
    parser.add_argument("path", type=Path, help="Ruta al archivo PDF/TXT")
    parser.add_argument("--slug", type=str, help="Slug opcional del paciente")
    args = parser.parse_args()

    asyncio.run(main(args.path, args.slug))
