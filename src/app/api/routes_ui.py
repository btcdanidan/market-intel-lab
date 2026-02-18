from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

UI_DIR = Path(__file__).resolve().parent.parent / "ui"

router = APIRouter(include_in_schema=False)


@router.get("/")
def ui_index() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")
