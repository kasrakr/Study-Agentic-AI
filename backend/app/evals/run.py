"""Command line entry point:  python -m app.evals.run [options]   (run from the backend directory)

Uses your real OpenAI-compatible endpoint (and Tavily, if configured), so it costs a small amount of API credit.
It indexes the sample documents in evals/documents into a temporary store, never into your own library.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from app.config import ConfigurationError, get_settings
from app.evals.dataset import EVALS_DIR, load_questions
from app.evals.runner import run_evaluation
from app.logging_config import configure_logging


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def print_report(report: dict) -> None:
    s, c = report["summary"], report["config"]
    print(f"\nModels: chat={c['chat_model']} embeddings={c['embedding_model']} retrieval={c['retrieval_mode']} (top_k={c['top_k']})")
    print(f"Endpoint: {c['endpoint']}   Web search configured: {c['web_search_configured']}\n")
    r = s["retrieval"]
    print(f"Retrieval ({r['evaluated']} questions with an expected document): hit rate {_pct(r['hit_rate'])}, MRR {r['mrr']}")
    if report.get("retrieval_comparison"):
        for mode, v in report["retrieval_comparison"].items():
            print(f"  {mode:<7} hit rate {_pct(v['hit_rate'])}, MRR {v['mrr']}")
    if s["questions"] and any("answer" in q or "error" in q for q in report["questions"]):
        f, ci, w, lat, tok = s["faithfulness"], s["citations"], s["web_search"], s["latency_ms"], s["token_usage"]
        print(f"Faithfulness ({f['judged']} judged by LLM): all claims supported {_pct(f['all_claims_supported_rate'])}, key-fact recall {_pct(f['key_fact_recall'])}")
        print(f"Citations ({ci['answers_with_citations']} answers): valid {_pct(ci['valid_rate'])}, cite an expected document {_pct(ci['cites_expected_document_rate'])}")
        print(f"Web decision accuracy {_pct(w['decision_accuracy'])}: used when needed {w['correct_use']}, avoided when unneeded {w['correct_avoid']}, "
              f"missed {w['missed_web']}, unnecessary {w['unnecessary_web']}")
        print(f"Latency ms: mean {lat['mean']}, median {lat['median']}, max {lat['max']}   Tokens: {tok['total'] if tok['total'] is not None else 'not reported'}")
    print()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate Study AI Agent on evals/questions.jsonl")
    ap.add_argument("--limit", type=int, help="only the first N questions")
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM faithfulness judge (saves tokens)")
    ap.add_argument("--retrieval-only", action="store_true", help="only measure retrieval (embeddings only, no chat calls)")
    ap.add_argument("--compare-retrieval", action="store_true", help="also compare vector vs hybrid retrieval")
    ap.add_argument("--mode", choices=["vector", "hybrid"], help="retrieval mode for the answering run (default: your RETRIEVAL_MODE)")
    ap.add_argument("--out", help="write the JSON report here (default: evals/results/eval-<time>.json)")
    args = ap.parse_args(argv)

    settings = get_settings()
    try:
        settings.validate_for_startup()
    except ConfigurationError as exc:
        print(exc)
        return 1
    if args.mode:
        settings = settings.model_copy(update={"retrieval_mode": args.mode})
    configure_logging(settings)

    questions = load_questions()[: args.limit]
    report = run_evaluation(
        questions, EVALS_DIR / "documents", settings=settings, judge=not args.no_judge,
        answer_questions=not args.retrieval_only, compare_retrieval=args.compare_retrieval or args.retrieval_only,
        on_progress=lambda n, total, qid: print(f"[{n}/{total}] {qid}", flush=True))
    report["created_at"] = datetime.now().isoformat(timespec="seconds")

    out = args.out or str(EVALS_DIR / "results" / f"eval-{datetime.now():%Y%m%d-%H%M%S}.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print_report(report)
    print(f"Full report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
