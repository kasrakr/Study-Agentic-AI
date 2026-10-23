// Mirrors backend/app/schemas/*. Keep in sync when backend schemas change.

export interface ApiErrorBody {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface HealthStatus {
  status: "ok";
  version: string;
  openai_configured: boolean;
  tavily_configured: boolean;
  chat_model: string;
  embedding_model: string;
  indexed_documents: number;
}

export interface ProbeResult {
  model: string;
  ok: boolean;
  error: { code: string; message: string } | null;
}

export interface OpenAIHealth {
  ok: boolean;
  embedding: ProbeResult;
  chat: ProbeResult;
}

export type DocumentStatus = "processing" | "indexed" | "failed";

export interface StudyDocument {
  id: string;
  filename: string;
  file_type: "pdf" | "txt" | "md";
  size_bytes: number;
  page_count: number | null;
  chunk_count: number;
  status: DocumentStatus;
  error_message: string | null;
  embedding_model: string | null;
  uploaded_at: string;
  indexed_at: string | null;
}

export interface UploadResponse {
  document: StudyDocument;
  duplicate: boolean;
}

export interface DocumentList {
  documents: StudyDocument[];
  total: number;
}

export interface ChatRequest {
  question: string;
  conversation_id?: string;
  document_ids?: string[];
}

export interface Citation {
  source_type: "document";
  source_number: number;
  document_id: string;
  filename: string;
  page_number: number | null;
  chunk_id: string;
  snippet: string;
  score: number;
}

export interface ChatResponse {
  conversation_id: string;
  answer: string;
  citations: Citation[];
  retrieval_path: string[];
  evidence_found: boolean;
  limitations: string | null;
  retrieved_count: number;
  latency_ms: number;
}
