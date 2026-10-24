from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.progress import ProgressOut
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
def get_progress(db: Session = Depends(get_db)) -> ProgressOut:
    """Quiz scores, flashcard ratings, weak topics (with the rule used), suggestions and recent activity."""
    return ProgressService(db).get_progress()
