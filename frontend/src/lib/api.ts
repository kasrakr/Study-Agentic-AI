// Central API client. The browser only ever talks to our FastAPI backend;
// OpenAI and Tavily keys live exclusively on the Python side.
import type {
  ApiErrorBody,
  AttemptResult,
  CardDifficulty,
  ChatRequest,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  Deck,
  DocumentList,
  Flashcard,
  HealthStatus,
  OpenAIHealth,
  Quiz,
  QuizAnswer,
  QuizGenerateRequest,
  StreamEvent,
  StudyDocument,
  UploadResponse,
} from "@/types/api";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the backend at ${API_BASE_URL}. Is it running?`, 0, "network_error");
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (body as { error?: ApiErrorBody } | null)?.error;
    throw new ApiError(
      error?.message ?? `Request failed (${response.status}).`,
      response.status,
      error?.code ?? "http_error",
      error?.details ?? {},
    );
  }
  return body as T;
}

const json = (data: unknown, signal?: AbortSignal, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
  signal,
});

async function toApiError(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null);
  const error = (body as { error?: ApiErrorBody } | null)?.error;
  return new ApiError(
    error?.message ?? `Request failed (${response.status}).`,
    response.status,
    error?.code ?? "http_error",
    error?.details ?? {},
  );
}

/**
 * POST /api/chat/stream. EventSource can't send a POST body, so this reads the SSE stream via fetch.
 * Abort the signal to cancel (the backend stops when the connection closes). Yields typed events.
 */
export async function* streamChat(body: ChatRequest, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat/stream`, json(body, signal));
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the backend at ${API_BASE_URL}. Is it running?`, 0, "network_error");
  }
  if (!response.ok) throw await toApiError(response);
  if (!response.body) throw new ApiError("The server sent no stream.", response.status, "no_stream");

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  let sawTerminal = false;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const parsed = parseSseBlock(block);
        if (!parsed) continue;
        if (parsed.event === "done" || parsed.event === "error") sawTerminal = true;
        yield parsed;
      }
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError("The connection to the server was lost.", 0, "stream_interrupted");
  }
  if (!sawTerminal) throw new ApiError("The connection to the server was lost.", 0, "stream_interrupted");
}

function parseSseBlock(block: string): StreamEvent | null {
  let event = "";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7);
    else if (line.startsWith("data: ")) data.push(line.slice(6));
  }
  if (!event || data.length === 0) return null;
  return { event, data: JSON.parse(data.join("\n")) } as StreamEvent;
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthStatus>("/api/health", { signal }),
  verifyOpenAI: (signal?: AbortSignal) => request<OpenAIHealth>("/api/health/openai", { signal }),

  listDocuments: (signal?: AbortSignal) => request<DocumentList>("/api/documents", { signal }),
  getDocument: (id: string) => request<StudyDocument>(`/api/documents/${encodeURIComponent(id)}`),
  deleteDocument: (id: string) =>
    request<{ id: string; deleted: boolean }>(`/api/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  uploadDocument: (file: File, signal?: AbortSignal) => {
    const form = new FormData();
    form.append("file", file);
    return request<UploadResponse>("/api/documents/upload", { method: "POST", body: form, signal });
  },

  documentFileUrl: (id: string, page?: number | null) =>
    `${API_BASE_URL}/api/documents/${encodeURIComponent(id)}/file${page ? `#page=${page}` : ""}`,

  chat: (body: ChatRequest, signal?: AbortSignal) => request<ChatResponse>("/api/chat", json(body, signal)),
  listConversations: (signal?: AbortSignal) =>
    request<{ conversations: ConversationSummary[] }>("/api/conversations", { signal }),
  getConversation: (id: string, signal?: AbortSignal) =>
    request<ConversationDetail>(`/api/conversations/${encodeURIComponent(id)}`, { signal }),
  deleteConversation: (id: string) =>
    request<{ id: string; deleted: boolean }>(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),

  generateQuiz: (body: QuizGenerateRequest, signal?: AbortSignal) =>
    request<Quiz>("/api/quizzes/generate", json(body, signal)),
  getQuiz: (id: string, signal?: AbortSignal) => request<Quiz>(`/api/quizzes/${encodeURIComponent(id)}`, { signal }),
  submitQuiz: (id: string, answers: QuizAnswer[]) =>
    request<AttemptResult>(`/api/quizzes/${encodeURIComponent(id)}/submit`, json({ answers })),

  generateFlashcards: (body: { document_ids: string[]; card_count?: number; topic?: string }, signal?: AbortSignal) =>
    request<Deck>("/api/flashcards/generate", json(body, signal)),
  getDeck: (id: string, signal?: AbortSignal) => request<Deck>(`/api/flashcards/${encodeURIComponent(id)}`, { signal }),
  rateCard: (cardId: string, difficulty: CardDifficulty) =>
    request<Flashcard>(`/api/flashcards/cards/${encodeURIComponent(cardId)}/difficulty`, json({ difficulty }, undefined, "PUT")),
};
