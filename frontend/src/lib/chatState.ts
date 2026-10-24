// Pure state logic for the chat so streaming behaviour can be unit-tested without React.
import type { AnswerOrigin, Artifact, Citation, StoredMessage, StreamEvent } from "@/types/api";

/** Plain-language labels for the steps the backend actually runs. */
export const STEP_LABELS: Record<string, string> = {
  classify_intent: "Understanding your question",
  retrieve_documents: "Searching your uploaded documents",
  grade_document_evidence: "Evaluating the retrieved passages",
  rewrite_query: "Rewording the search",
  identify_missing_information: "Web fallback required: working out what’s missing",
  web_search: "Searching external sources",
  grade_web_evidence: "Evaluating web results",
  generate_answer: "Generating a grounded answer",
  respond_smalltalk: "Replying",
  generate_quiz: "Creating a quiz from your documents",
  generate_flashcards: "Creating flashcards from your documents",
};

export interface StepState {
  step: string;
  label: string;
  phase: "running" | "done";
  detail: string | null;
  durationMs: number | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: "streaming" | "done" | "stopped" | "error";
  steps: StepState[];
  citations: Citation[];
  answerOrigin: AnswerOrigin | null;
  webSearchUsed: boolean;
  webSearchError: string | null;
  limitations: string | null;
  artifact: Artifact | null;
  error: string | null;
  latencyMs: number | null;
}

export function userMessage(id: string, content: string): ChatMessage {
  return { ...blank(id, "user"), content, status: "done" };
}

export function pendingAssistant(id: string): ChatMessage {
  return blank(id, "assistant");
}

function blank(id: string, role: ChatMessage["role"]): ChatMessage {
  return {
    id, role, content: "", status: "streaming", steps: [], citations: [], answerOrigin: null, webSearchUsed: false,
    webSearchError: null, limitations: null, artifact: null, error: null, latencyMs: null,
  };
}

export function applyStreamEvent(msg: ChatMessage, ev: StreamEvent): ChatMessage {
  switch (ev.event) {
    case "status": {
      const { step, phase, detail, duration_ms } = ev.data;
      const label = STEP_LABELS[step] ?? step;
      if (phase === "started") {
        return { ...msg, steps: [...msg.steps, { step, label, phase: "running", detail: null, durationMs: null }] };
      }
      // Complete the most recent running step with this name (a retry produces a second one).
      const steps = [...msg.steps];
      for (let i = steps.length - 1; i >= 0; i--) {
        if (steps[i].step === step && steps[i].phase === "running") {
          steps[i] = { ...steps[i], phase: "done", detail, durationMs: duration_ms };
          return { ...msg, steps };
        }
      }
      return { ...msg, steps: [...steps, { step, label, phase: "done", detail, durationMs: duration_ms }] };
    }
    case "token":
      return { ...msg, content: msg.content + ev.data.text };
    case "sources":
      return {
        ...msg, content: ev.data.answer, citations: ev.data.citations, answerOrigin: ev.data.answer_origin,
        webSearchUsed: ev.data.web_search_used, webSearchError: ev.data.web_search_error, limitations: ev.data.limitations,
      };
    case "done":
      return { ...msg, status: "done", artifact: ev.data.artifact, latencyMs: ev.data.latency_ms };
    case "error":
      return { ...msg, status: "error", error: ev.data.message };
  }
}

/** Rebuild messages from a saved conversation (step timings aren't stored, only which steps ran). */
export function fromStored(m: StoredMessage, id: string): ChatMessage {
  const base = blank(id, m.role);
  if (m.role === "user") return { ...base, content: m.content, status: "done" };
  return {
    ...base, content: m.content, status: "done", citations: m.citations, answerOrigin: m.answer_origin as AnswerOrigin | null,
    webSearchUsed: m.web_search_used, limitations: m.limitations, artifact: m.artifact,
    steps: m.retrieval_path.map((step) => ({ step, label: STEP_LABELS[step] ?? step, phase: "done", detail: null, durationMs: null })),
  };
}

export function totalSeconds(steps: StepState[]): number | null {
  const ms = steps.reduce((sum, s) => sum + (s.durationMs ?? 0), 0);
  return ms > 0 ? ms / 1000 : null;
}

/** Turn [D1] / [W2] markers into markdown links with a cite: scheme so they can be rendered as chips. */
export function linkifyMarkers(text: string): string {
  return text.replace(/\[([DW]\d+)\]/g, "[$1](cite:$1)");
}
