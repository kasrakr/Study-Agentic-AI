"""Quiz generation, storage, scoring and grading."""

from __future__ import annotations

import logging
import random
import re
import uuid

from langchain_core.language_models import BaseChatModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import prompts
from app.config import Settings
from app.db.models import Quiz, QuizAnswer, QuizAttempt, QuizQuestion, utcnow
from app.errors import AppError, NotFoundError
from app.rag.indexer import VectorIndex
from app.resilience import invoke_structured
from app.schemas.quizzes import (
    AnswerIn,
    AttemptResult,
    QuestionResult,
    QuizDraft,
    QuizOut,
    QuizQuestionDraft,
    QuizQuestionOut,
    ShortAnswerGrades,
    SourceRef,
)
from app.services.study_material import Passage, collect_passages

logger = logging.getLogger(__name__)

MAX_GENERATION_ATTEMPTS = 2  # one initial call plus at most one top-up
# A short answer counts as "correct" (for weak-topic tracking) at or above this fraction of rubric points.
SHORT_ANSWER_CORRECT_THRESHOLD = 0.6
MODEL_GRADING_NOTE = (
    "Short-answer questions were graded by an AI model against a rubric. "
    "Treat those marks as an estimate; multiple-choice and true/false are marked automatically."
)


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def validate_draft(draft: QuizQuestionDraft, allowed_types: list[str], passages: list[Passage]) -> dict | None:
    """Return a normalised question dict, or None if the model's output is unusable."""
    if draft.type not in allowed_types:
        return None
    question = draft.question.strip()
    explanation = draft.explanation.strip()
    if not question or len(question) > 1000 or not explanation:
        return None
    if not 1 <= draft.source_number <= len(passages):
        return None

    if draft.type == "multiple_choice":
        options = [o.strip() for o in draft.options]
        if len(options) != 4 or any(not o for o in options) or len({_norm(o) for o in options}) != 4:
            return None
        if draft.correct_option_index is None or not 0 <= draft.correct_option_index <= 3:
            return None
        key: dict = {"correct_option_index": draft.correct_option_index}
    elif draft.type == "true_false":
        if draft.correct_boolean is None:
            return None
        options, key = ["True", "False"], {"correct": draft.correct_boolean}
    else:
        reference = (draft.reference_answer or "").strip()
        points = [k.strip() for k in draft.key_points if k.strip()]
        if not reference or not 1 <= len(points) <= 6:
            return None
        options, key = [], {"reference_answer": reference, "key_points": points}

    return {"type": draft.type, "question": question, "options": options, "answer_key": key,
            "explanation": explanation, "topic": (draft.topic.strip() or "General")[:120],
            "passage": passages[draft.source_number - 1]}


def _shuffle_options(q: dict, rng: random.Random) -> None:
    """Models tend to put the right answer first or in the middle; shuffle and re-point the key."""
    if q["type"] != "multiple_choice":
        return
    correct_text = q["options"][q["answer_key"]["correct_option_index"]]
    rng.shuffle(q["options"])
    q["answer_key"] = {"correct_option_index": q["options"].index(correct_text)}


class QuizService:
    def __init__(self, db: Session, index: VectorIndex, chat_model: BaseChatModel, settings: Settings,
                 rng: random.Random | None = None) -> None:
        self.db, self.index, self.chat_model, self.settings = db, index, chat_model, settings
        self.rng = rng or random.Random()

    # ------------------------------------------------------------ generation
    def generate(self, *, document_ids: list[str], question_count: int, question_types: list[str],
                 difficulty: str, topic: str | None) -> Quiz:
        if question_count > self.settings.quiz_max_questions:
            raise AppError(f"At most {self.settings.quiz_max_questions} questions can be generated at once.",
                           status_code=422, code="too_many_questions")
        passages = collect_passages(self.index, document_ids, limit=self.settings.generation_context_chunks, topic=topic,
                                    mode=self.settings.retrieval_mode)
        passage_text = prompts.format_quiz_passages(passages)

        accepted: list[dict] = []
        seen: set[str] = set()
        for _attempt in range(MAX_GENERATION_ATTEMPTS):
            missing = question_count - len(accepted)
            if missing <= 0:
                break
            avoid = ""
            if accepted:
                avoid = "Do not repeat these existing questions:\n" + "\n".join(f"- {q['question']}" for q in accepted) + "\n"
            draft = invoke_structured(
                self.chat_model, QuizDraft, prompts.QUIZ_SYSTEM,
                prompts.QUIZ_HUMAN.format(
                    count=missing, types=", ".join(question_types), difficulty=difficulty,
                    topic_line=f"Focus on: {topic}\n" if topic else "", avoid_line=avoid, passages=passage_text),
                max_retries=self.settings.openai_max_retries,
            )
            for d in draft.questions:
                q = validate_draft(d, question_types, passages)
                if q is None or _norm(q["question"]) in seen:
                    continue
                seen.add(_norm(q["question"]))
                accepted.append(q)
                if len(accepted) == question_count:
                    break
        if not accepted:
            raise AppError("The model did not produce any valid questions. Please try again.",
                           status_code=502, code="quiz_generation_failed")
        for q in accepted:
            _shuffle_options(q, self.rng)

        quiz = Quiz(id=uuid.uuid4().hex, title=self._title(document_ids, topic), difficulty=difficulty,
                    document_ids=document_ids, created_at=utcnow())
        self.db.add(quiz)
        self.db.flush()
        for position, q in enumerate(accepted, start=1):
            p: Passage = q["passage"]
            self.db.add(QuizQuestion(
                id=uuid.uuid4().hex, quiz_id=quiz.id, position=position, type=q["type"], question=q["question"],
                options=q["options"], answer_key=q["answer_key"], explanation=q["explanation"], topic=q["topic"],
                document_id=p.document_id, filename=p.filename, page_number=p.page_number, chunk_id=p.chunk_id))
        self.db.commit()
        logger.info("Generated quiz %s with %d/%d questions", quiz.id, len(accepted), question_count)
        return quiz

    def _title(self, document_ids: list[str], topic: str | None) -> str:
        return f"Quiz: {topic}" if topic else f"Quiz on {len(document_ids)} document{'s' if len(document_ids) != 1 else ''}"

    # ------------------------------------------------------------ reading
    def _questions(self, quiz_id: str) -> list[QuizQuestion]:
        return list(self.db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id).order_by(QuizQuestion.position)))

    def get_quiz(self, quiz_id: str) -> QuizOut:
        quiz = self.db.get(Quiz, quiz_id)
        if quiz is None:
            raise NotFoundError("Quiz not found.", details={"quiz_id": quiz_id})
        return self.to_out(quiz)

    def to_out(self, quiz: Quiz) -> QuizOut:
        questions = self._questions(quiz.id)
        return QuizOut(
            id=quiz.id, title=quiz.title, difficulty=quiz.difficulty, document_ids=quiz.document_ids,
            question_count=len(questions), created_at=quiz.created_at,
            questions=[QuizQuestionOut(id=q.id, position=q.position, type=q.type, question=q.question,
                                       options=q.options, topic=q.topic) for q in questions])

    # ------------------------------------------------------------ submission
    def submit(self, quiz_id: str, answers: list[AnswerIn]) -> AttemptResult:
        quiz = self.db.get(Quiz, quiz_id)
        if quiz is None:
            raise NotFoundError("Quiz not found.", details={"quiz_id": quiz_id})
        questions = self._questions(quiz_id)
        by_id = {q.id: q for q in questions}
        unknown = [a.question_id for a in answers if a.question_id not in by_id]
        if unknown:
            raise AppError("Some answers refer to questions that are not in this quiz.",
                           status_code=422, code="unknown_question", details={"question_ids": unknown})
        given = {a.question_id: a for a in answers}

        scored: dict[str, dict] = {q.id: self._score_objective(q, given.get(q.id)) for q in questions if q.type != "short_answer"}
        self._grade_short_answers([q for q in questions if q.type == "short_answer"], given, scored)

        attempt = QuizAttempt(id=uuid.uuid4().hex, quiz_id=quiz_id, submitted_at=utcnow(), points=0.0,
                              max_points=float(len(questions)), score_percent=0.0,
                              graded_by_model=any(s["graded_by"] == "model" for s in scored.values()))
        attempt.points = round(sum(s["points"] for s in scored.values()), 2)
        attempt.score_percent = round(100 * attempt.points / attempt.max_points, 1) if questions else 0.0
        self.db.add(attempt)
        self.db.flush()

        results: list[QuestionResult] = []
        for q in questions:
            s = scored[q.id]
            self.db.add(QuizAnswer(attempt_id=attempt.id, question_id=q.id, response=s["your_answer"],
                                   is_correct=s["is_correct"], points=s["points"], feedback=s["feedback"],
                                   graded_by=s["graded_by"]))
            results.append(QuestionResult(
                question_id=q.id, position=q.position, type=q.type, question=q.question, options=q.options,
                topic=q.topic, your_answer=s["your_answer"], correct_answer=self._correct_text(q),
                is_correct=s["is_correct"], points=s["points"], graded_by=s["graded_by"], feedback=s["feedback"],
                explanation=q.explanation,
                source=SourceRef(document_id=q.document_id, filename=q.filename, page_number=q.page_number)))
        self.db.commit()
        return AttemptResult(
            attempt_id=attempt.id, quiz_id=quiz_id, points=attempt.points, max_points=attempt.max_points,
            score_percent=attempt.score_percent, graded_by_model=attempt.graded_by_model,
            grading_note=MODEL_GRADING_NOTE if attempt.graded_by_model else None, results=results)

    @staticmethod
    def _correct_text(q: QuizQuestion) -> str:
        if q.type == "multiple_choice":
            return q.options[q.answer_key["correct_option_index"]]
        if q.type == "true_false":
            return "True" if q.answer_key["correct"] else "False"
        return q.answer_key["reference_answer"]

    @staticmethod
    def _unanswered() -> dict:
        return {"your_answer": None, "is_correct": None, "points": 0.0, "feedback": None, "graded_by": "unanswered"}

    def _score_objective(self, q: QuizQuestion, a: AnswerIn | None) -> dict:
        """Deterministic marking for multiple-choice and true/false. No model involved."""
        if q.type == "multiple_choice":
            if a is None or a.selected_option is None:
                return self._unanswered()
            if a.selected_option >= len(q.options):
                raise AppError("Selected option is out of range.", status_code=422, code="invalid_answer",
                               details={"question_id": q.id})
            correct = a.selected_option == q.answer_key["correct_option_index"]
            shown = q.options[a.selected_option]
        else:
            if a is None or a.boolean_answer is None:
                return self._unanswered()
            correct = a.boolean_answer == q.answer_key["correct"]
            shown = "True" if a.boolean_answer else "False"
        return {"your_answer": shown, "is_correct": correct, "points": 1.0 if correct else 0.0,
                "feedback": None, "graded_by": "auto"}

    def _grade_short_answers(self, questions: list[QuizQuestion], given: dict[str, AnswerIn], scored: dict[str, dict]) -> None:
        pending: list[tuple[QuizQuestion, str]] = []
        for q in questions:
            a = given.get(q.id)
            text = (a.text_answer or "").strip() if a else ""
            if text:
                pending.append((q, text))
            else:
                scored[q.id] = self._unanswered()
        if not pending:
            return
        items = [{"question": q.question, "reference_answer": q.answer_key["reference_answer"],
                  "key_points": q.answer_key["key_points"], "answer": text} for q, text in pending]
        result = invoke_structured(
            self.chat_model, ShortAnswerGrades, prompts.GRADE_SHORT_SYSTEM,
            prompts.GRADE_SHORT_HUMAN.format(items=prompts.format_grading_items(items)),
            max_retries=self.settings.openai_max_retries)
        by_item = {g.item: g for g in result.grades}
        for n, (q, text) in enumerate(pending, start=1):
            grade = by_item.get(n)
            total = len(q.answer_key["key_points"])
            # Score is computed here from the model's per-point judgements, never taken from it directly.
            if grade is None or len(grade.key_point_results) != total:
                raise AppError("The grader returned an unusable result. Please submit again.",
                               status_code=502, code="invalid_model_output")
            fraction = sum(grade.key_point_results) / total
            scored[q.id] = {"your_answer": text, "is_correct": fraction >= SHORT_ANSWER_CORRECT_THRESHOLD,
                            "points": round(fraction, 2), "feedback": grade.feedback.strip() or None, "graded_by": "model"}
