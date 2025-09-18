from __future__ import annotations

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select

from common.config import settings
from common.db import IFOMItem, init_db, get_session


def adapt_case(case: Dict[str, Any], index: int) -> Dict[str, Any]:
    options = case.get("options", [])
    if not options:
        raise ValueError(f"Case {index} no tiene opciones")

    answer_index = next((i for i, opt in enumerate(options) if opt.get("is_correct")), None)
    if answer_index is None:
        raise ValueError(f"Case {index} no tiene respuesta correcta marcada")

    internal_id = str(case.get("id") or case.get("slug") or f"case-{index}")

    internal = {
        "id": internal_id,
        "stem": case.get("stem") or case.get("question") or "Caso sin enunciado",
        "options": [opt.get("text", "") for opt in options],
        "answer_index": answer_index,
        "explanation": case.get("explanation") or case.get("rationale") or "",
        "tags": case.get("tags") or [],
    }
    return internal


async def persist_items(items: List[Dict[str, Any]]) -> None:
    await init_db()
    async with get_session() as session:
        for payload in items:
            stmt = select(IFOMItem).where(IFOMItem.external_id == payload["id"])
            existing = await session.scalar(stmt)
            if existing:
                existing.stem = payload["stem"]
                existing.options = payload["options"]
                existing.answer_index = payload["answer_index"]
                existing.explanation = payload["explanation"]
                existing.tags = payload["tags"]
            else:
                session.add(
                    IFOMItem(
                        external_id=payload["id"],
                        stem=payload["stem"],
                        options=payload["options"],
                        answer_index=payload["answer_index"],
                        explanation=payload["explanation"],
                        tags=payload["tags"],
                    )
                )
        await session.commit()


async def main(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if not cases:
        raise ValueError("El JSON no contiene 'cases'")

    items = [adapt_case(case, idx) for idx, case in enumerate(cases, start=1)]
    await persist_items(items)
    print(f"Se cargaron {len(items)} ítems IFOM")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed IFOM bank")
    parser.add_argument("--path", type=Path, default=Path(settings.ifom_json_path), help="Ruta al JSON original")
    args = parser.parse_args()

    asyncio.run(main(args.path))
