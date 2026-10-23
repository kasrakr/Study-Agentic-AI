// Central API client. The browser only ever talks to our FastAPI backend;
// OpenAI and Tavily keys live exclusively on the Python side.
import type {
  ApiErrorBody,
  ChatRequest,
  ChatResponse,
  DocumentList,
  HealthStatus,
  OpenAIHealth,
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

const json = (data: unknown, signal?: AbortSignal): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
  signal,
});

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

  chat: (body: ChatRequest, signal?: AbortSignal) => request<ChatResponse>("/api/chat", json(body, signal)),
};
