from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_quiz_service, get_document_service
from app.schemas.common import ErrorResponse
from app.schemas.quizzes import AttemptResult, QuizGenerateRequest, QuizOut, QuizSubmitRequest
from app.services.document_service import DocumentService
from app.services.quiz_service import QuizService

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])
_ERRORS = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}}


@router.post("/generate", response_model=QuizOut, status_code=201, responses=_ERRORS)
def generate_quiz(
    body: QuizGenerateRequest,
    documents: DocumentService = Depends(get_document_service),
    quizzes: QuizService = Depends(get_quiz_service),
) -> QuizOut:
    """Generate a quiz from the selected documents only (no web content). The response
    has no answer key; answers and explanations are returned on submit."""
    documents.require_indexed(body.document_ids)
    quiz = quizzes.generate(
        document_ids=list(dict.fromkeys(body.document_ids)), question_count=body.question_count,
        question_types=body.question_types, difficulty=body.difficulty, topic=body.topic)
    return quizzes.to_out(quiz)


@router.get("/{quiz_id}", response_model=QuizOut, responses=_ERRORS)
def get_quiz(quiz_id: str, quizzes: QuizService = Depends(get_quiz_service)) -> QuizOut:
    return quizzes.get_quiz(quiz_id)


@router.post("/{quiz_id}/submit", response_model=AttemptResult, responses=_ERRORS)
def submit_quiz(
    quiz_id: str, body: QuizSubmitRequest, quizzes: QuizService = Depends(get_quiz_service)
) -> AttemptResult:
    """Score an attempt. Multiple-choice/true-false are marked automatically; short answers are
    graded by the model against a rubric and flagged as model-graded."""
    return quizzes.submit(quiz_id, body.answers)
