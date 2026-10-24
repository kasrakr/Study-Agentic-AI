"""End-to-end smoke test against a RUNNING backend (use this with your real API keys).

    python scripts/smoke_live.py [--base http://localhost:8000] [--skip-study-tools] [--keep]

It uploads a small sample document, asks questions through the real pipeline, checks the structure and
traceability of the results, then deletes what it created. Costs a few cents of API credit.

Side effects that can't be undone through the API: with study tools enabled it creates one quiz attempt and
one flashcard deck, which will show in your Dashboard progress. Use --skip-study-tools to avoid that.

Result levels:  PASS  ok  |  WARN  worked, but model behaviour differed from what we expect  |  FAIL  a real problem
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

SAMPLE = Path(__file__).resolve().parents[2] / "evals" / "documents" / "photosynthesis.md"
COVERED_Q = "Where in the chloroplast do the light-dependent reactions occur?"
UNCOVERED_Q = "Who won the most recent FIFA World Cup?"

results: list[tuple[str, str, str]] = []


def record(level: str, name: str, detail: str = "") -> bool:
    results.append((level, name, detail))
    print(f"[{level:<4}] {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return level != "FAIL"


def error_of(res: httpx.Response) -> str:
    try:
        e = res.json()["error"]
        return f'{e["code"]}: {e["message"]}'
    except Exception:  # noqa: BLE001
        return f"HTTP {res.status_code}: {res.text[:200]}"


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


def run(base: str, skip_tools: bool, keep: bool) -> None:
    http = httpx.Client(base_url=base, timeout=180)
    created_doc: str | None = None
    conversations: list[str] = []

    try:
        # 1. health
        try:
            health = http.get("/api/health").json()
        except httpx.HTTPError as exc:
            record("FAIL", "backend reachable", f"{type(exc).__name__}: is it running at {base}?")
            return
        record("PASS" if health.get("openai_configured") else "FAIL", "backend up, OpenAI key configured",
               f'endpoint {health.get("openai_base_url")}, chat={health.get("chat_model")}, embeddings={health.get("embedding_model")}')
        tavily = bool(health.get("tavily_configured"))

        # 2. real model connectivity
        res = http.get("/api/health/openai").json()
        for part in ("embedding", "chat"):
            ok = res[part]["ok"]
            record("PASS" if ok else "FAIL", f"{part} model reachable", res[part]["model"] if ok else res[part]["error"]["message"])
        if not res["ok"]:
            return

        # 3. upload (+ duplicate detection)
        up = http.post("/api/documents/upload", files={"file": (SAMPLE.name, SAMPLE.read_bytes(), "text/markdown")})
        if up.status_code not in (200, 201):
            record("FAIL", "upload and index sample document", error_of(up))
            return
        doc = up.json()["document"]
        created_doc = doc["id"] if not up.json()["duplicate"] else None
        record("PASS" if doc["status"] == "indexed" and doc["chunk_count"] > 0 else "FAIL", "upload and index sample document",
               f'{doc["chunk_count"]} passage(s)' + (" (already in your library)" if up.json()["duplicate"] else ""))
        again = http.post("/api/documents/upload", files={"file": (SAMPLE.name, SAMPLE.read_bytes(), "text/markdown")})
        record("PASS" if again.status_code == 200 and again.json()["duplicate"] else "FAIL", "re-upload is detected as duplicate")

        # 4. covered question: document-first, cited, no web
        ask = http.post("/api/chat", json={"question": COVERED_Q, "document_ids": [doc["id"]]})
        if ask.status_code != 200:
            record("FAIL", "ask a covered question", error_of(ask))
        else:
            body = ask.json()
            conversations.append(body["conversation_id"])
            docs = [c for c in body["citations"] if c["source_type"] == "document"]
            record("PASS" if docs and all(c["filename"] == SAMPLE.name for c in docs) else "FAIL",
                   "answer cites the uploaded document", f'{len(docs)} citation(s), path: {" > ".join(body["retrieval_path"])}')
            record("PASS" if not body["web_search_used"] else "WARN", "web search avoided when documents suffice")
            record("PASS" if "thylakoid" in body["answer"].lower() else "WARN", "answer content looks right (mentions thylakoid)")
            record("PASS" if body["answer_origin"] == "documents" else "WARN", "answer origin reported as documents", body["answer_origin"])

            follow = http.post("/api/chat", json={"question": "And where does the Calvin cycle happen?",
                                                  "conversation_id": body["conversation_id"], "document_ids": [doc["id"]]})
            detail = http.get(f'/api/conversations/{body["conversation_id"]}').json()
            record("PASS" if follow.status_code == 200 and len(detail["messages"]) == 4 else "FAIL",
                   "follow-up stays in the same, persisted conversation", error_of(follow) if follow.status_code != 200 else "")

        # 5. streaming
        stream = http.post("/api/chat/stream", json={"question": COVERED_Q, "document_ids": [doc["id"]]})
        if stream.status_code != 200:
            record("FAIL", "streaming endpoint", error_of(stream))
        else:
            events = parse_sse(stream.text)
            kinds = [e for e, _ in events]
            tokens = "".join(d["text"] for e, d in events if e == "token")
            ok = kinds[-2:] == ["sources", "done"] and bool(tokens) and "status" in kinds
            record("PASS" if ok else "FAIL", "SSE stream: statuses, tokens, sources, done",
                   f'{kinds.count("status")} status, {kinds.count("token")} token events' if ok else f"events: {kinds[-4:]}")
            if "done" in kinds:
                conversations.append(dict(events)["done"]["conversation_id"])

        # 6. question the documents can't answer: web fallback, honest about it
        out = http.post("/api/chat", json={"question": UNCOVERED_Q, "document_ids": [doc["id"]]})
        if out.status_code != 200:
            record("FAIL", "ask a question the documents don't cover", error_of(out))
        else:
            body = out.json()
            conversations.append(body["conversation_id"])
            web = [c for c in body["citations"] if c["source_type"] == "web"]
            record("PASS" if all(c["url"].startswith(("http://", "https://")) for c in web) else "FAIL", "web citations carry real URLs", f"{len(web)} web source(s)")
            if tavily:
                record("PASS" if body["web_search_used"] else "WARN", "web fallback used for an uncovered question",
                       body["web_search_error"] or "")
                record("PASS" if not [c for c in body["citations"] if c["source_type"] == "document"] else "WARN",
                       "document sources not attached to a web-only answer")
            else:
                record("PASS" if "TAVILY_API_KEY" in (body["web_search_error"] or "") and not web else "FAIL",
                       "without a Tavily key: reports the limitation, invents nothing", body["limitations"] or "")
                record("WARN", "Tavily not configured, so the live web path was NOT exercised", "set TAVILY_API_KEY and re-run")

        # 7. quiz + flashcards + progress
        if skip_tools:
            record("WARN", "quiz / flashcards skipped (--skip-study-tools)")
        else:
            quiz = http.post("/api/quizzes/generate", json={"document_ids": [doc["id"]], "question_count": 3, "question_types": ["multiple_choice", "true_false"]})
            if quiz.status_code != 201:
                record("FAIL", "generate a quiz", error_of(quiz))
            else:
                q = quiz.json()
                no_key = all(set(x) == {"id", "position", "type", "question", "options", "topic"} for x in q["questions"])
                record("PASS" if q["questions"] and no_key else "FAIL", "quiz generated without leaking the answer key", f'{len(q["questions"])} question(s)')
                answers = [{"question_id": x["id"], **({"selected_option": 0} if x["type"] == "multiple_choice" else {"boolean_answer": True})} for x in q["questions"]]
                sub = http.post(f'/api/quizzes/{q["id"]}/submit', json={"answers": answers})
                record("PASS" if sub.status_code == 200 and 0 <= sub.json()["score_percent"] <= 100 else "FAIL", "submit quiz and receive a score",
                       f'{sub.json()["score_percent"]}%' if sub.status_code == 200 else error_of(sub))
            deck = http.post("/api/flashcards/generate", json={"document_ids": [doc["id"]], "card_count": 3})
            if deck.status_code != 201:
                record("FAIL", "generate flashcards", error_of(deck))
            else:
                cards = deck.json()["cards"]
                rate = http.put(f'/api/flashcards/cards/{cards[0]["id"]}/difficulty', json={"difficulty": "medium"})
                record("PASS" if cards and rate.status_code == 200 else "FAIL", "flashcards generated and rated", f"{len(cards)} card(s)")
        prog = http.get("/api/progress")
        record("PASS" if prog.status_code == 200 else "FAIL", "progress endpoint", "" if prog.status_code == 200 else error_of(prog))
    finally:
        if not keep:
            for cid in dict.fromkeys(conversations):
                http.delete(f"/api/conversations/{cid}")
            if created_doc:
                gone = http.delete(f"/api/documents/{created_doc}")
                record("PASS" if gone.status_code == 200 else "WARN", "cleanup: sample document and conversations removed")
        http.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--skip-study-tools", action="store_true")
    ap.add_argument("--keep", action="store_true", help="do not delete the sample document and conversations afterwards")
    args = ap.parse_args()
    run(args.base.rstrip("/"), args.skip_study_tools, args.keep)
    counts = {lvl: sum(1 for r in results if r[0] == lvl) for lvl in ("PASS", "WARN", "FAIL")}
    print(f"\n{counts['PASS']} passed, {counts['WARN']} warnings, {counts['FAIL']} failed")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
