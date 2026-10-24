"""Learning progress computed directly from stored quiz attempts and flashcard ratings.

Weak-topic rule (deliberately simple and transparent):
  For each topic label, data_points = answered quiz questions + rated flashcards.
  A topic is flagged when data_points >= MIN_DATA_POINTS and
  (incorrect answers + cards rated "difficult") / data_points >= WEAK_SHARE.
Nothing here estimates "mastery"; it only reports what the student got wrong or found hard.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    STATUS_INDEXED,
    Conversation,
    Document,
    Flashcard,
    FlashcardDeck,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
)
from app.schemas.progress import (
    ActivityItem,
    DocumentRef,
    FlashcardStats,
    ProgressOut,
    QuizStats,
    RecentAttempt,
    Suggestion,
    WeakTopic,
)

MIN_DATA_POINTS = 2
WEAK_SHARE = 0.5
MAX_WEAK_TOPICS = 5
RECENT_LIMIT = 8

METHOD = (
    "A topic is flagged when you have at least 2 results on it (answered quiz questions plus rated flashcards) "
    "and at least half of them were answered incorrectly or marked 'difficult'. Topic labels are written by the "
    "model when it creates questions and cards, so similar topics may be split. Every quiz attempt counts, "
    "including repeats of the same quiz."
)


class ProgressService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_progress(self) -> ProgressOut:
        weak, note = self._weak_topics()
        return ProgressOut(
            indexed_documents=self.db.scalar(select(func.count()).select_from(Document).where(Document.status == STATUS_INDEXED)) or 0,
            quiz=self._quiz_stats(),
            flashcards=self._flashcard_stats(),
            weak_topics=weak,
            weak_topics_method=METHOD,
            weak_topics_note=note,
            suggestions=[
                Suggestion(kind="practice_quiz", topic=w.topic, document_ids=[d.document_id for d in w.documents],
                           reason=f"{w.incorrect_answers} incorrect and {w.difficult_cards} difficult out of {w.data_points} results")
                for w in weak[:3] if w.documents
            ],
            recent_activity=self._activity(),
        )

    # ------------------------------------------------------------ quizzes
    def _quiz_stats(self) -> QuizStats:
        total, avg, best = self.db.execute(
            select(func.count(QuizAttempt.id), func.avg(QuizAttempt.score_percent), func.max(QuizAttempt.score_percent))
        ).one()
        rows = self.db.execute(
            select(QuizAttempt, Quiz.title).join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .order_by(QuizAttempt.submitted_at.desc()).limit(RECENT_LIMIT)
        ).all()
        return QuizStats(
            attempts=total, average_score_percent=round(avg, 1) if avg is not None else None,
            best_score_percent=best,
            recent=[RecentAttempt(attempt_id=a.id, quiz_id=a.quiz_id, quiz_title=title, score_percent=a.score_percent,
                                  points=a.points, max_points=a.max_points, graded_by_model=a.graded_by_model,
                                  submitted_at=a.submitted_at) for a, title in rows],
        )

    def _flashcard_stats(self) -> FlashcardStats:
        decks = self.db.scalar(select(func.count()).select_from(FlashcardDeck)) or 0
        counts = dict(self.db.execute(
            select(Flashcard.difficulty, func.count()).where(Flashcard.difficulty.is_not(None)).group_by(Flashcard.difficulty)).all())
        return FlashcardStats(decks=decks, rated=sum(counts.values()), easy=counts.get("easy", 0),
                              medium=counts.get("medium", 0), difficult=counts.get("difficult", 0))

    # ------------------------------------------------------------ weak topics
    def _weak_topics(self) -> tuple[list[WeakTopic], str | None]:
        stats: dict[str, dict] = defaultdict(lambda: {"labels": Counter(), "points": 0, "wrong": 0, "hard": 0, "docs": Counter()})

        answers = self.db.execute(
            select(QuizQuestion.topic, QuizAnswer.is_correct, QuizQuestion.document_id)
            .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
            .where(QuizAnswer.is_correct.is_not(None))
        ).all()
        for topic, correct, doc_id in answers:
            s = stats[topic.strip().lower()]
            s["labels"][topic.strip()] += 1
            s["points"] += 1
            if not correct:
                s["wrong"] += 1
                s["docs"][doc_id] += 1

        cards = self.db.execute(
            select(Flashcard.topic, Flashcard.difficulty, Flashcard.document_id).where(Flashcard.difficulty.is_not(None))
        ).all()
        for topic, difficulty, doc_id in cards:
            s = stats[topic.strip().lower()]
            s["labels"][topic.strip()] += 1
            s["points"] += 1
            if difficulty == "difficult":
                s["hard"] += 1
                s["docs"][doc_id] += 1

        existing = {d.id: d.filename for d in self.db.scalars(select(Document).where(Document.status == STATUS_INDEXED))}
        flagged: list[WeakTopic] = []
        for s in stats.values():
            if s["points"] < MIN_DATA_POINTS:
                continue
            share = (s["wrong"] + s["hard"]) / s["points"]
            if share >= WEAK_SHARE:
                flagged.append(WeakTopic(
                    topic=s["labels"].most_common(1)[0][0], data_points=s["points"], incorrect_answers=s["wrong"],
                    difficult_cards=s["hard"], weak_share=round(share, 2),
                    documents=[DocumentRef(document_id=d, filename=existing[d]) for d, _ in s["docs"].most_common() if d in existing]))
        flagged.sort(key=lambda w: (w.weak_share, w.data_points), reverse=True)

        total_points = sum(s["points"] for s in stats.values())
        note = None
        if total_points == 0:
            note = "No quiz answers or rated flashcards yet, so there is nothing to base weak topics on."
        elif not flagged and total_points < 10:
            note = "Only a few results so far. Weak topics appear once a topic has at least 2 results and half are wrong or difficult."
        return flagged[:MAX_WEAK_TOPICS], note

    # ------------------------------------------------------------ activity
    def _activity(self) -> list[ActivityItem]:
        items: list[ActivityItem] = []
        for d in self.db.scalars(select(Document).where(Document.status == STATUS_INDEXED).order_by(Document.uploaded_at.desc()).limit(RECENT_LIMIT)):
            items.append(ActivityItem(type="upload", title=f"Uploaded {d.filename}", at=d.indexed_at or d.uploaded_at, ref_id=d.id))
        for c in self.db.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(RECENT_LIMIT)):
            items.append(ActivityItem(type="chat", title=c.title, at=c.updated_at, ref_id=c.id))
        for a, title in self.db.execute(select(QuizAttempt, Quiz.title).join(Quiz, Quiz.id == QuizAttempt.quiz_id)
                                        .order_by(QuizAttempt.submitted_at.desc()).limit(RECENT_LIMIT)):
            items.append(ActivityItem(type="quiz", title=f"{title}: {a.score_percent:g}%", at=a.submitted_at, ref_id=a.quiz_id))
        for deck in self.db.scalars(select(FlashcardDeck).order_by(FlashcardDeck.created_at.desc()).limit(RECENT_LIMIT)):
            items.append(ActivityItem(type="flashcards", title=deck.title, at=deck.created_at, ref_id=deck.id))
        items.sort(key=lambda i: i.at, reverse=True)
        return items[:RECENT_LIMIT]
