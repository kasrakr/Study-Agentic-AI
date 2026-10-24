import pytest

from app.evals import metrics
from app.evals.dataset import EVALS_DIR, load_questions
from app.evals.runner import Judgement, run_evaluation

CATEGORIES = {"covered", "exact_term", "partial", "not_covered", "explicit_external"}


# ---------------------------------------------------------------- dataset

def test_dataset_is_well_formed_and_self_contained():
    questions = load_questions()
    assert len(questions) >= 10
    docs = {p.name for p in (EVALS_DIR / "documents").iterdir()}
    for q in questions:
        assert q.category in CATEGORIES and q.question.strip() and q.reference_answer.strip()
        assert set(q.expected_documents) <= docs, f"{q.id} references a missing document"
        if q.category in ("not_covered", "explicit_external", "partial"):
            assert q.needs_web, f"{q.id} should expect web search"
        if q.category in ("covered", "exact_term"):
            assert not q.needs_web and q.expected_documents and q.key_facts
    assert {q.category for q in questions} == CATEGORIES  # every behaviour is represented


# ---------------------------------------------------------------- metrics

def test_retrieval_outcome():
    assert metrics.retrieval_outcome(["a.md", "b.md", "c.md"], ["b.md"]) == {"hit": True, "rank": 2, "reciprocal_rank": 0.5}
    assert metrics.retrieval_outcome(["a.md"], ["z.md"]) == {"hit": False, "rank": None, "reciprocal_rank": 0.0}
    assert metrics.retrieval_outcome(["a.md"], []) is None


@pytest.mark.parametrize("needs,used,expected", [(True, True, "correct_use"), (True, False, "missed_web"),
                                                 (False, True, "unnecessary_web"), (False, False, "correct_avoid")])
def test_web_decision(needs, used, expected):
    assert metrics.web_decision(needs, used) == expected


def doc_cite(chunk_id="c1", filename="a.md", doc_id="doc_1", snippet="Alpha beta gamma"):
    return {"source_type": "document", "marker": "D1", "chunk_id": chunk_id, "filename": filename,
            "document_id": doc_id, "snippet": snippet, "url": None}


def check(citations, stored=None, urls=frozenset(), expected=("a.md",)):
    stored = stored if stored is not None else {"c1": ("Alpha beta  gamma delta", {"filename": "a.md", "document_id": "doc_1"})}
    return metrics.check_citations(citations, expected_documents=list(expected), stored_chunks=stored, web_urls_returned=set(urls))


def test_valid_document_citation_tolerates_whitespace_and_truncation_marker():
    r = check([doc_cite(snippet="Alpha beta gamma…")])
    assert r["valid"] and r["cites_expected"] is True and r["unexpected_documents"] == []


@pytest.mark.parametrize("cite,problem", [
    (doc_cite(chunk_id="ghost"), "chunk not found"),
    (doc_cite(filename="b.md"), "metadata mismatch"),
    (doc_cite(snippet="invented text"), "snippet is not from the chunk"),
])
def test_invalid_document_citations_are_detected(cite, problem):
    r = check([cite])
    assert not r["valid"] and problem in r["invalid"][0]


def test_web_citation_must_come_from_the_search_results():
    web = {"source_type": "web", "marker": "W1", "url": "https://x.test/a", "chunk_id": None, "snippet": "s"}
    assert check([web], urls={"https://x.test/a"})["valid"]
    assert not check([web], urls={"https://other.test"})["valid"]


def test_citing_an_unexpected_document_is_reported():
    stored = {"c1": ("Alpha beta gamma", {"filename": "other.md", "document_id": "doc_1"})}
    r = check([doc_cite(filename="other.md")], stored=stored)
    assert r["valid"] and r["cites_expected"] is False and r["unexpected_documents"] == ["other.md"]


def test_summarize_aggregates_correctly():
    rows = [
        {"retrieval": {"hit": True, "rank": 1, "reciprocal_rank": 1.0}, "web_decision": "correct_avoid", "latency_ms": 100,
         "citation_check": {"citations": 1, "valid": True, "cites_expected": True},
         "judge": {"all_claims_supported": True, "key_facts_covered": [True, False]}, "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}},
        {"retrieval": {"hit": False, "rank": None, "reciprocal_rank": 0.0}, "web_decision": "missed_web", "latency_ms": 300,
         "citation_check": {"citations": 0, "valid": True, "cites_expected": None}, "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}},
    ]
    s = metrics.summarize(rows)
    assert s["retrieval"] == {"evaluated": 2, "hit_rate": 0.5, "mrr": 0.5}
    assert s["faithfulness"]["all_claims_supported_rate"] == 1.0 and s["faithfulness"]["key_fact_recall"] == 0.5
    assert s["citations"]["answers_with_citations"] == 1  # answers without citations aren't scored here
    assert s["web_search"]["decision_accuracy"] == 0.5 and s["web_search"]["missed_web"] == 1
    assert s["latency_ms"] == {"mean": 200, "median": 200, "max": 300}
    assert s["token_usage"]["total"] == 17


# ---------------------------------------------------------------- full offline run

@pytest.fixture
def judged_chat(chat_model):
    chat_model.responders["Judgement"] = lambda m: Judgement(all_claims_supported=True, unsupported_claims=[], key_facts_covered=[True])
    return chat_model


def test_full_run_with_fakes_produces_a_complete_isolated_report(settings, embeddings, judged_chat, web):
    questions = load_questions()
    report = run_evaluation(questions, EVALS_DIR / "documents", settings=settings, embeddings=embeddings,
                            chat_model=judged_chat, web_search=web, judge=True, compare_retrieval=True)
    assert [q["id"] for q in report["questions"]] == [q.id for q in questions]
    s = report["summary"]
    assert s["retrieval"]["evaluated"] == 11 and s["retrieval"]["hit_rate"] >= 0.7  # bag-of-words fakes still find most sources
    assert s["citations"]["valid_rate"] == 1.0  # every citation is traceable to a stored chunk or returned URL
    assert s["web_search"]["missed_web"] == 3 and s["web_search"]["correct_avoid"] >= 8  # default fake grader never asks for the web
    assert s["latency_ms"]["mean"] is not None and s["token_usage"]["total"] is None  # fakes report no usage
    assert set(report["retrieval_comparison"]) == {"vector", "hybrid"}
    assert report["config"]["documents"] == sorted(p.name for p in (EVALS_DIR / "documents").iterdir())
    assert "sk-" not in str(report) and "openai_api_key" not in str(report).lower()
    assert not list(settings.upload_path.glob("*"))  # the evaluation never touched the configured stores


def test_run_measures_unnecessary_web_use(settings, embeddings, judged_chat, web):
    from app.agent.schemas import DocumentGrade
    judged_chat.responders["DocumentGrade"] = lambda m: DocumentGrade(
        verdict="partial", reason="r", relevant_passages=[1], missing_information=["x"], retrieval_may_have_missed=False)
    report = run_evaluation(load_questions()[:3], EVALS_DIR / "documents", settings=settings, embeddings=embeddings,
                            chat_model=judged_chat, web_search=web, judge=False)
    assert report["summary"]["web_search"]["unnecessary_web"] == 3 and len(web.calls) == 3
    assert report["summary"]["faithfulness"]["judged"] == 0  # judge disabled


def test_retrieval_only_mode_makes_no_chat_calls(settings, embeddings, chat_model, web):
    report = run_evaluation(load_questions(), EVALS_DIR / "documents", settings=settings, embeddings=embeddings,
                            chat_model=chat_model, web_search=web, answer_questions=False, compare_retrieval=True)
    assert sum(chat_model.calls.values()) == 0 and web.calls == []
    assert report["summary"]["web_search"]["decision_accuracy"] is None
    assert report["retrieval_comparison"]["vector"]["evaluated"] == 11


def test_cli_report_prints_and_cli_refuses_without_a_key(settings, embeddings, judged_chat, web, capsys, monkeypatch):
    from app.evals import run as cli
    report = run_evaluation(load_questions()[:4], EVALS_DIR / "documents", settings=settings, embeddings=embeddings,
                            chat_model=judged_chat, web_search=web, compare_retrieval=True)
    cli.print_report(report)
    out = capsys.readouterr().out
    assert "Retrieval (" in out and "vector" in out and "hybrid" in out and "Web decision accuracy" in out and "Latency ms" in out

    monkeypatch.setattr(cli, "get_settings", lambda: settings.model_copy(update={"openai_api_key": None}))
    assert cli.main(["--limit", "1"]) == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().out
