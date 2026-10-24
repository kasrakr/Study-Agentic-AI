"""Flashcard generation, storage and difficulty marking."""

from __future__ import annotations

import logging
import re
import uuid

from langchain_core.language_models import BaseChatModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import prompts
from app.config import Settings
from app.db.models import Flashcard, FlashcardDeck, utcnow
from app.errors import AppError, NotFoundError
from app.rag.indexer import VectorIndex
from app.resilience import invoke_structured
from app.schemas.flashcards import DeckOut, FlashcardOut, FlashcardSet
from app.services.study_material import collect_passages

logger = logging.getLogger(__name__)

MAX_GENERATION_ATTEMPTS = 2


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


class FlashcardService:
    def __init__(self, db: Session, index: VectorIndex, chat_model: BaseChatModel, settings: Settings) -> None:
        self.db, self.index, self.chat_model, self.settings = db, index, chat_model, settings

    def generate(self, *, document_ids: list[str], card_count: int, topic: str | None) -> FlashcardDeck:
        if card_count > self.settings.flashcard_max_cards:
            raise AppError(f"At most {self.settings.flashcard_max_cards} cards can be generated at once.",
                           status_code=422, code="too_many_cards")
        passages = collect_passages(self.index, document_ids, limit=self.settings.generation_context_chunks, topic=topic,
                                    mode=self.settings.retrieval_mode)
        passage_text = prompts.format_quiz_passages(passages)

        accepted: list[tuple] = []
        seen: set[str] = set()
        for _ in range(MAX_GENERATION_ATTEMPTS):
            missing = card_count - len(accepted)
            if missing <= 0:
                break
            avoid = ""
            if accepted:
                avoid = "Do not repeat these existing cards:\n" + "\n".join(f"- {d.front}" for d, _ in accepted) + "\n"
            out = invoke_structured(
                self.chat_model, FlashcardSet, prompts.FLASHCARD_SYSTEM,
                prompts.FLASHCARD_HUMAN.format(count=missing, topic_line=f"Focus on: {topic}\n" if topic else "",
                                               avoid_line=avoid, passages=passage_text),
                max_retries=self.settings.openai_max_retries)
            for d in out.cards:
                front, back = d.front.strip(), d.back.strip()
                if not front or not back or not 1 <= d.source_number <= len(passages) or _norm(front) in seen:
                    continue
                seen.add(_norm(front))
                accepted.append((d, passages[d.source_number - 1]))
                if len(accepted) == card_count:
                    break
        if not accepted:
            raise AppError("The model did not produce any valid flashcards. Please try again.",
                           status_code=502, code="flashcard_generation_failed")

        deck = FlashcardDeck(id=uuid.uuid4().hex, title=f"Flashcards: {topic}" if topic else "Flashcards",
                             document_ids=document_ids, created_at=utcnow())
        self.db.add(deck)
        self.db.flush()
        for position, (d, p) in enumerate(accepted, start=1):
            self.db.add(Flashcard(
                id=uuid.uuid4().hex, deck_id=deck.id, position=position, front=d.front.strip(), back=d.back.strip(),
                topic=(d.topic.strip() or "General")[:120], document_id=p.document_id, filename=p.filename,
                page_number=p.page_number, chunk_id=p.chunk_id))
        self.db.commit()
        logger.info("Generated flashcard deck %s with %d cards", deck.id, len(accepted))
        return deck

    def to_out(self, deck: FlashcardDeck) -> DeckOut:
        cards = self.db.scalars(select(Flashcard).where(Flashcard.deck_id == deck.id).order_by(Flashcard.position)).all()
        return DeckOut(id=deck.id, title=deck.title, document_ids=deck.document_ids, created_at=deck.created_at,
                       cards=[self._card_out(c) for c in cards])

    @staticmethod
    def _card_out(c: Flashcard) -> FlashcardOut:
        return FlashcardOut(id=c.id, position=c.position, front=c.front, back=c.back, topic=c.topic,
                            document_id=c.document_id, filename=c.filename, page_number=c.page_number,
                            difficulty=c.difficulty, rated_at=c.rated_at)  # type: ignore[arg-type]

    def get_deck(self, deck_id: str) -> DeckOut:
        deck = self.db.get(FlashcardDeck, deck_id)
        if deck is None:
            raise NotFoundError("Flashcard deck not found.", details={"deck_id": deck_id})
        return self.to_out(deck)

    def rate_card(self, card_id: str, difficulty: str) -> FlashcardOut:
        card = self.db.get(Flashcard, card_id)
        if card is None:
            raise NotFoundError("Flashcard not found.", details={"card_id": card_id})
        card.difficulty, card.rated_at = difficulty, utcnow()
        self.db.commit()
        return self._card_out(card)
