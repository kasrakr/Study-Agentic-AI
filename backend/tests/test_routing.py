"""Conditional-routing logic, tested directly as pure functions."""

import pytest

from app.agent.routing import route_after_classify, route_after_document_grade, route_after_rewrite
from app.agent.state import RESET, merge_events


def grade_state(**kw):
    base = {"evidence_verdict": "insufficient", "retrieval_may_have_missed": False, "retry_count": 0,
            "retrieved_document_chunks": [{"chunk_id": "c1"}], "wants_web": False}
    return {**base, **kw}


def route(state, max_retries=1):
    return route_after_document_grade(state, max_retries=max_retries)


def test_smalltalk_skips_retrieval_everything_else_searches_documents_first():
    assert route_after_classify({"intent": "smalltalk"}) == "respond_smalltalk"
    for intent in ("study_question", "explain_simply"):
        assert route_after_classify({"intent": intent}) == "retrieve_documents"


def test_sufficient_evidence_goes_straight_to_answer_never_web():
    assert route(grade_state(evidence_verdict="sufficient")) == "generate_answer"
    # even if the grader also suggested a retry
    assert route(grade_state(evidence_verdict="sufficient", retrieval_may_have_missed=True)) == "generate_answer"


@pytest.mark.parametrize("verdict", ["partial", "insufficient"])
def test_incomplete_evidence_goes_to_web_path_when_no_retry_is_useful(verdict):
    assert route(grade_state(evidence_verdict=verdict)) == "identify_missing_information"


def test_retry_only_when_it_may_help_and_budget_remains():
    assert route(grade_state(retrieval_may_have_missed=True)) == "rewrite_query"
    assert route(grade_state(retrieval_may_have_missed=True, retry_count=1)) == "identify_missing_information"
    assert route(grade_state(retrieval_may_have_missed=True), max_retries=0) == "identify_missing_information"
    assert route(grade_state(retrieval_may_have_missed=True, retrieved_document_chunks=[])) == "identify_missing_information"


def test_explicit_external_request_goes_to_web_even_with_sufficient_documents():
    assert route(grade_state(evidence_verdict="sufficient", wants_web=True)) == "identify_missing_information"


def test_unchanged_rewrite_does_not_loop():
    assert route_after_rewrite({"query_changed": True}) == "retrieve_documents"
    assert route_after_rewrite({"query_changed": False}) == "identify_missing_information"


def test_event_reducer_resets_between_turns_and_appends_within_a_turn():
    first = merge_events([{"step": "old"}], [{"step": RESET}])
    assert first == []
    assert merge_events(first, [{"step": "a"}]) == [{"step": "a"}]
    assert merge_events([{"step": "a"}], [{"step": "b"}]) == [{"step": "a"}, {"step": "b"}]
