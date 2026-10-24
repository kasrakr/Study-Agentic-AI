import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MessageBubble from "@/components/chat/MessageBubble";
import { applyStreamEvent, pendingAssistant, type ChatMessage } from "@/lib/chatState";
import StudyChat from "@/pages/StudyChat";
import type { Citation, StreamEvent } from "@/types/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    streamChat: vi.fn(),
    api: { ...actual.api, listDocuments: vi.fn(), listConversations: vi.fn(), getConversation: vi.fn(), deleteConversation: vi.fn() },
  };
});
import { api, streamChat } from "@/lib/api";

const doc: Citation = { source_type: "document", marker: "D1", snippet: "Mitochondria make ATP.", score: 0.6, document_id: "doc_1",
  filename: "bio.pdf", page_number: 3, chunk_id: "c1", title: null, url: null };
const web: Citation = { source_type: "web", marker: "W1", snippet: "Osmosis is...", score: 0.9, document_id: null, filename: null,
  page_number: null, chunk_id: null, title: "Osmosis explained", url: "https://www.example.edu/osmosis" };

function assistant(overrides: Partial<ChatMessage>): ChatMessage {
  return { ...pendingAssistant("m1"), status: "done", ...overrides };
}

describe("MessageBubble", () => {
  it("shows document and web sources in separate, labelled sections with real links", () => {
    render(<MemoryRouter><MessageBubble message={assistant({
      content: "Notes say ATP [D1]. The web adds osmosis [W1].", citations: [doc, web], answerOrigin: "documents_and_web", webSearchUsed: true,
      steps: [{ step: "generate_answer", label: "x", phase: "done", detail: null, durationMs: 10 }],
    })} /></MemoryRouter>);

    expect(screen.getByText("Answered from your documents and the web")).toBeInTheDocument();
    const docs = screen.getByRole("region", { name: "Sources from your documents" });
    const webSection = screen.getByRole("region", { name: "Sources from the web" });
    const docLink = within(docs).getByRole("link", { name: "bio.pdf" });
    expect(docLink).toHaveAttribute("href", expect.stringMatching(/\/api\/documents\/doc_1\/file#page=3$/));
    expect(within(docs).getByText("page 3")).toBeInTheDocument();
    const webLink = within(webSection).getByRole("link", { name: "Osmosis explained" });
    expect(webLink).toHaveAttribute("href", "https://www.example.edu/osmosis");
    expect(webLink).toHaveAttribute("target", "_blank");
    expect(webLink).toHaveAttribute("rel", expect.stringContaining("noopener"));
    expect(within(webSection).getByText("example.edu")).toBeInTheDocument();
    // Origins never mix: each section holds only its own markers and links.
    expect(within(docs).getByText("D1")).toBeInTheDocument();
    expect(within(docs).queryByText("W1")).toBeNull();
    expect(within(docs).getAllByRole("link")).toHaveLength(1);
    expect(within(webSection).getByText("W1")).toBeInTheDocument();
    expect(within(webSection).queryByText("D1")).toBeNull();
    expect(within(webSection).getAllByRole("link")).toHaveLength(1);
  });

  it("renders markers as chips that highlight their source when clicked", async () => {
    render(<MemoryRouter><MessageBubble message={assistant({ content: "ATP [D1].", citations: [doc], answerOrigin: "documents" })} /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: "Document source D1" }));
    expect(document.getElementById("src-m1-D1")).toHaveClass("ring-2");
  });

  it("never renders model-written links or raw HTML", () => {
    const { container } = render(<MemoryRouter><MessageBubble message={assistant({
      content: "See [my page](https://evil.test/login) <img src=x onerror=alert(1)> and <script>alert(1)</script> **bold**",
      citations: [], answerOrigin: "none" })} /></MemoryRouter>);
    expect(screen.queryByRole("link")).toBeNull();
    expect(container.querySelector("img, script")).toBeNull();
    expect(screen.getByText("my page")).toBeInTheDocument(); // text kept, link dropped
    expect(container.querySelector("strong")).toHaveTextContent("bold");
  });

  it("flags limitations, failed web search and uncited answers", () => {
    render(<MemoryRouter><MessageBubble message={assistant({
      content: "Partial answer [D1].", citations: [doc], answerOrigin: "documents", webSearchUsed: true,
      limitations: "Web search did not help: The web search timed out.",
      steps: [{ step: "generate_answer", label: "x", phase: "done", detail: null, durationMs: 1 }] })} /></MemoryRouter>);
    expect(screen.getByText("Limitations")).toBeInTheDocument();
    expect(screen.getByText(/timed out/)).toBeInTheDocument();
    expect(screen.getByText("Web search was tried but its results weren’t used")).toBeInTheDocument();
  });

  it("links to a generated quiz and shows errors and stopped state", () => {
    const { rerender } = render(<MemoryRouter><MessageBubble message={assistant({ content: "Made one.", artifact: { type: "quiz", id: "q9" } })} /></MemoryRouter>);
    expect(screen.getByRole("link", { name: /Open the quiz/ })).toHaveAttribute("href", "/quiz?quiz=q9");
    rerender(<MemoryRouter><MessageBubble message={assistant({ status: "error", error: "Rate limit exceeded." })} /></MemoryRouter>);
    expect(screen.getByRole("alert")).toHaveTextContent("Rate limit exceeded.");
    rerender(<MemoryRouter><MessageBubble message={assistant({ status: "stopped", content: "partial" })} /></MemoryRouter>);
    expect(screen.getByText(/Stopped/)).toBeInTheDocument();
  });

  it("shows live activity while streaming and a collapsed summary afterwards, flagging web search", () => {
    let m = pendingAssistant("m1");
    m = applyStreamEvent(m, { event: "status", data: { status: "retrieving_documents", step: "retrieve_documents", phase: "started", detail: null, duration_ms: null } });
    const { rerender } = render(<MemoryRouter><MessageBubble message={m} /></MemoryRouter>);
    expect(screen.getByLabelText("Agent activity")).toHaveTextContent("Searching your uploaded documents");
    expect(screen.getByLabelText("in progress")).toBeInTheDocument();

    const done = assistant({ steps: [
      { step: "retrieve_documents", label: "Searching your uploaded documents", phase: "done", detail: "6 passages found", durationMs: 100 },
      { step: "web_search", label: "Searching external sources", phase: "done", detail: "5 results", durationMs: 900 }] });
    rerender(<MemoryRouter><MessageBubble message={done} /></MemoryRouter>);
    expect(screen.getByText(/Agent activity · 2 steps/)).toBeInTheDocument();
    expect(screen.getByText(/web search used/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- StudyChat page

const indexedDoc = { id: "doc_1", filename: "bio.pdf", file_type: "pdf", size_bytes: 10, page_count: 2, chunk_count: 3, status: "indexed",
  error_message: null, embedding_model: "m", uploaded_at: "2026-01-01T00:00:00Z", indexed_at: "2026-01-01T00:00:00Z" };

function scripted(events: StreamEvent[]) {
  return async function* () { for (const e of events) yield e; };
}
const status = (step: string, phase: "started" | "completed", detail: string | null = null): StreamEvent => ({
  event: "status", data: { status: step, step, phase, detail, duration_ms: phase === "completed" ? 50 : null } });

beforeEach(() => {
  vi.mocked(api.listDocuments).mockResolvedValue({ documents: [indexedDoc], total: 1 } as never);
  vi.mocked(api.listConversations).mockResolvedValue({ conversations: [] });
  vi.mocked(streamChat).mockReset();
});

describe("StudyChat", () => {
  it("streams an answer with a timeline and citations, scoped to the selected documents", async () => {
    vi.mocked(streamChat).mockImplementation(scripted([
      status("retrieve_documents", "started"), status("retrieve_documents", "completed", "3 passages found; best similarity 0.62"),
      status("generate_answer", "started"),
      { event: "token", data: { text: "Mitochondria make " } }, { event: "token", data: { text: "ATP [D1]." } },
      status("generate_answer", "completed", "answer from documents; 1 citations"),
      { event: "sources", data: { answer: "Mitochondria make ATP [D1].", citations: [doc], answer_origin: "documents", web_search_used: false, web_search_error: null, limitations: null } },
      { event: "done", data: { conversation_id: "c1", intent: "study_question", retrieval_path: [], execution_events: [], evidence_found: true, artifact: null, latency_ms: 800 } },
    ]) as never);
    render(<MemoryRouter><StudyChat /></MemoryRouter>);

    await userEvent.click(await screen.findByText(/Searching all 1 document/));
    await userEvent.click(await screen.findByRole("checkbox", { name: /bio\.pdf/ }));
    await userEvent.type(screen.getByLabelText(/Ask a question/), "What do mitochondria make?{Enter}");

    expect(await screen.findByText("Answered from your documents")).toBeInTheDocument();
    expect(screen.getByText("What do mitochondria make?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Document source D1" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "bio.pdf" })).toHaveAttribute("href", expect.stringContaining("#page=3"));
    expect(screen.getByText(/Agent activity · 2 steps/)).toBeInTheDocument();

    const [body] = vi.mocked(streamChat).mock.calls[0];
    expect(body).toMatchObject({ question: "What do mitochondria make?", document_ids: ["doc_1"] });
    expect(body.conversation_id).toMatch(/^[A-Za-z0-9_-]{1,64}$/);
  });

  it("keeps follow-ups in the same conversation", async () => {
    vi.mocked(streamChat).mockImplementation(scripted([
      { event: "done", data: { conversation_id: "c1", intent: "smalltalk", retrieval_path: [], execution_events: [], evidence_found: false, artifact: null, latency_ms: 1 } }]) as never);
    render(<MemoryRouter><StudyChat /></MemoryRouter>);
    const box = await screen.findByLabelText(/Ask a question/);
    await userEvent.type(box, "first{Enter}");
    await waitFor(() => expect(streamChat).toHaveBeenCalledTimes(1));
    await userEvent.type(box, "second{Enter}");
    await waitFor(() => expect(streamChat).toHaveBeenCalledTimes(2));
    const ids = vi.mocked(streamChat).mock.calls.map(([b]) => b.conversation_id);
    expect(ids[0]).toBe(ids[1]);
  });

  it("lets the student stop a running answer", async () => {
    vi.mocked(streamChat).mockImplementation((_body, signal) => (async function* () {
      yield status("retrieve_documents", "started");
      await new Promise<void>((_res, rej) => signal?.addEventListener("abort", () => rej(new DOMException("x", "AbortError"))));
    })() as never);
    render(<MemoryRouter><StudyChat /></MemoryRouter>);
    await userEvent.type(await screen.findByLabelText(/Ask a question/), "slow question{Enter}");
    await userEvent.click(await screen.findByRole("button", { name: "Stop generating" }));
    expect(await screen.findByText(/Stopped/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send message" })).toBeInTheDocument(); // composer is usable again
  });

  it("shows a sanitized error event and an unreachable backend", async () => {
    vi.mocked(streamChat).mockImplementationOnce(scripted([{ event: "error", data: { code: "openai_auth_failed", message: "The API key was rejected.", retryable: false } }]) as never);
    render(<MemoryRouter><StudyChat /></MemoryRouter>);
    await userEvent.type(await screen.findByLabelText(/Ask a question/), "q1{Enter}");
    expect(await screen.findByText("The API key was rejected.")).toBeInTheDocument();

    vi.mocked(streamChat).mockImplementationOnce(() => { throw new Error("Cannot reach the backend at http://localhost:8000. Is it running?"); });
    await userEvent.type(screen.getByLabelText(/Ask a question/), "q2{Enter}");
    expect(await screen.findByText(/Cannot reach the backend/)).toBeInTheDocument();
  });

  it("opens a saved conversation with its sources", async () => {
    vi.mocked(api.listConversations).mockResolvedValue({ conversations: [{ id: "c9", title: "Old chat", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }] });
    vi.mocked(api.getConversation).mockResolvedValue({ conversation: { id: "c9", title: "Old chat", created_at: "", updated_at: "" }, messages: [
      { role: "user", content: "Earlier question", citations: [], answer_origin: null, retrieval_path: [], web_search_used: false, limitations: null, artifact: null },
      { role: "assistant", content: "Earlier answer [D1]", citations: [doc], answer_origin: "documents", retrieval_path: ["classify_intent", "generate_answer"], web_search_used: false, limitations: null, artifact: null }] });
    render(<MemoryRouter><StudyChat /></MemoryRouter>);
    const buttons = await screen.findAllByRole("button", { name: /Old chat/ });
    await userEvent.click(buttons[0]);
    expect(await screen.findByText("Earlier question")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "bio.pdf" })).toBeInTheDocument();
  });

  it("guides the student to upload documents when there are none", async () => {
    vi.mocked(api.listDocuments).mockResolvedValue({ documents: [], total: 0 });
    render(<MemoryRouter><StudyChat /></MemoryRouter>);
    expect(await screen.findByText(/haven’t indexed any documents/)).toBeInTheDocument();
  });
});
