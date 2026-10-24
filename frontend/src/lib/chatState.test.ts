import { describe, expect, it } from "vitest";
import { applyStreamEvent, fromStored, linkifyMarkers, pendingAssistant, totalSeconds } from "./chatState";
import type { Citation, StreamEvent } from "@/types/api";

const status = (step: string, phase: "started" | "completed", detail: string | null = null, ms: number | null = null): StreamEvent =>
  ({ event: "status", data: { status: step, step, phase, detail, duration_ms: ms } });

const docCite: Citation = { source_type: "document", marker: "D1", snippet: "s", score: 0.5, document_id: "doc_1", filename: "a.pdf",
  page_number: 3, chunk_id: "c1", title: null, url: null };

describe("applyStreamEvent", () => {
  it("tracks real steps from started to completed, with detail and duration", () => {
    let m = pendingAssistant("a");
    m = applyStreamEvent(m, status("retrieve_documents", "started"));
    expect(m.steps).toMatchObject([{ step: "retrieve_documents", phase: "running", label: "Searching your uploaded documents" }]);
    m = applyStreamEvent(m, status("retrieve_documents", "completed", "6 passages found", 120));
    expect(m.steps).toMatchObject([{ phase: "done", detail: "6 passages found", durationMs: 120 }]);
  });

  it("keeps a retried step as a second entry instead of overwriting the first", () => {
    let m = pendingAssistant("a");
    for (const phase of ["started", "completed", "started", "completed"] as const) m = applyStreamEvent(m, status("retrieve_documents", phase));
    expect(m.steps).toHaveLength(2);
    expect(m.steps.every((s) => s.phase === "done")).toBe(true);
  });

  it("accumulates tokens, then replaces the text with the validated final answer from the sources event", () => {
    let m = pendingAssistant("a");
    m = applyStreamEvent(m, { event: "token", data: { text: "Real [D1] " } });
    m = applyStreamEvent(m, { event: "token", data: { text: "and fake [D9]." } });
    expect(m.content).toBe("Real [D1] and fake [D9].");
    m = applyStreamEvent(m, { event: "sources", data: { answer: "Real [D1] and fake.", citations: [docCite], answer_origin: "documents",
      web_search_used: false, web_search_error: null, limitations: null } });
    expect(m.content).toBe("Real [D1] and fake.");
    expect(m.citations).toEqual([docCite]);
    expect(m.answerOrigin).toBe("documents");
  });

  it("marks completion with latency and artifact, and surfaces errors without discarding partial text", () => {
    let m = applyStreamEvent(pendingAssistant("a"), { event: "token", data: { text: "partial" } });
    const failed = applyStreamEvent(m, { event: "error", data: { code: "openai_timeout", message: "Timed out.", retryable: true } });
    expect(failed).toMatchObject({ status: "error", error: "Timed out.", content: "partial" });
    m = applyStreamEvent(m, { event: "done", data: { conversation_id: "c", intent: "quiz", retrieval_path: [], execution_events: [],
      evidence_found: true, artifact: { type: "quiz", id: "q1" }, latency_ms: 900 } });
    expect(m).toMatchObject({ status: "done", latencyMs: 900, artifact: { type: "quiz", id: "q1" } });
  });
});

describe("helpers", () => {
  it("linkifies only well-formed source markers", () => {
    expect(linkifyMarkers("A [D1][W2] and [X1] and [D]")).toBe("A [D1](cite:D1)[W2](cite:W2) and [X1] and [D]");
  });

  it("restores a stored assistant message with its sources and the steps that ran", () => {
    const m = fromStored({ role: "assistant", content: "Hi [D1]", citations: [docCite], answer_origin: "documents",
      retrieval_path: ["classify_intent", "retrieve_documents"], web_search_used: false, limitations: null, artifact: null }, "x");
    expect(m).toMatchObject({ status: "done", citations: [docCite], answerOrigin: "documents" });
    expect(m.steps.map((s) => s.step)).toEqual(["classify_intent", "retrieve_documents"]);
  });

  it("sums step durations", () => {
    expect(totalSeconds([{ step: "a", label: "", phase: "done", detail: null, durationMs: 1500 }, { step: "b", label: "", phase: "done", detail: null, durationMs: 500 }])).toBe(2);
    expect(totalSeconds([])).toBeNull();
  });
});
