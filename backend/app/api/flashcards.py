from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_document_service, get_flashcard_service
from app.schemas.common import ErrorResponse
from app.schemas.flashcards import DeckOut, FlashcardGenerateRequest, FlashcardOut, RateCardRequest
from app.services.document_service import DocumentService
from app.services.flashcard_service import FlashcardService

router = APIRouter(prefix="/api/flashcards", tags=["flashcards"])
_ERRORS = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}}


@router.post("/generate", response_model=DeckOut, status_code=201, responses=_ERRORS)
def generate_flashcards(
    body: FlashcardGenerateRequest,
    documents: DocumentService = Depends(get_document_service),
    flashcards: FlashcardService = Depends(get_flashcard_service),
) -> DeckOut:
    documents.require_indexed(body.document_ids)
    deck = flashcards.generate(
        document_ids=list(dict.fromkeys(body.document_ids)), card_count=body.card_count, topic=body.topic)
    return flashcards.to_out(deck)


@router.get("/{deck_id}", response_model=DeckOut, responses=_ERRORS)
def get_deck(deck_id: str, flashcards: FlashcardService = Depends(get_flashcard_service)) -> DeckOut:
    return flashcards.get_deck(deck_id)


@router.put("/cards/{card_id}/difficulty", response_model=FlashcardOut, responses=_ERRORS)
def rate_card(
    card_id: str, body: RateCardRequest, flashcards: FlashcardService = Depends(get_flashcard_service)
) -> FlashcardOut:
    """Mark a card easy, medium or difficult (stored for progress tracking)."""
    return flashcards.rate_card(card_id, body.difficulty)
