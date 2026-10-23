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
  openai_base_url: string;
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

export type AnswerOrigin = "documents" | "web" | "documents_and_web" | "none";

/** A source the answer relies on. Document and web fields are mutually exclusive. */
export interface Citation {
  source_type: "document" | "web";
  marker: string; // "D1" / "W1": matches [D1] / [W1] in the answer text
  snippet: string;
  score: number | null;
  document_id: string | null;
  filename: string | null;
  page_number: number | null;
  chunk_id: string | null;
  title: string | null;
  url: string | null;
}

export interface ExecutionEvent {
  step: string;
  detail: string | null;
  duration_ms: number | null;
}

export interface Artifact {
  type: "quiz" | "flashcards";
  id: string;
}

export interface ChatResponse {
  conversation_id: string;
  intent: string;
  answer: string;
  citations: Citation[];
  answer_origin: AnswerOrigin;
  retrieval_path: string[];
  execution_events: ExecutionEvent[];
  evidence_found: boolean;
  web_search_used: boolean;
  web_search_error: string | null;
  limitations: string | null;
  artifact: Artifact | null;
  latency_ms: number;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  answer_origin: AnswerOrigin | null;
  retrieval_path: string[];
  web_search_used: boolean;
  limitations: string | null;
}

export interface ConversationDetail {
  conversation: ConversationSummary;
  messages: StoredMessage[];
}

// ---- Server-Sent Events from POST /api/chat/stream ----
export interface StatusEvent {
  status: string; // e.g. retrieving_documents, evaluating_evidence, searching_web, generating_answer
  step: string;
  phase: "started" | "completed";
  detail: string | null;
  duration_ms: number | null;
}

export interface SourcesEvent {
  answer: string; // final validated text; replaces the streamed text
  citations: Citation[];
  answer_origin: AnswerOrigin;
  web_search_used: boolean;
  web_search_error: string | null;
  limitations: string | null;
}

export interface DoneEvent {
  conversation_id: string;
  intent: string;
  retrieval_path: string[];
  execution_events: ExecutionEvent[];
  evidence_found: boolean;
  artifact: Artifact | null;
  latency_ms: number;
}

export interface StreamErrorEvent {
  code: string;
  message: string;
  retryable: boolean;
}

export type StreamEvent =
  | { event: "status"; data: StatusEvent }
  | { event: "token"; data: { text: string } }
  | { event: "sources"; data: SourcesEvent }
  | { event: "done"; data: DoneEvent }
  | { event: "error"; data: StreamErrorEvent };

// ---- Quizzes ----
export type QuestionType = "multiple_choice" | "true_false" | "short_answer";
export type QuizDifficulty = "easy" | "medium" | "hard";

export interface QuizGenerateRequest {
  document_ids: string[];
  question_count?: number;
  question_types?: QuestionType[];
  difficulty?: QuizDifficulty;
  topic?: string;
}

export interface QuizQuestion {
  id: string;
  position: number;
  type: QuestionType;
  question: string;
  options: string[];
  topic: string;
}

export interface Quiz {
  id: string;
  title: string;
  difficulty: QuizDifficulty;
  document_ids: string[];
  question_count: number;
  created_at: string;
  questions: QuizQuestion[];
}

export interface QuizAnswer {
  question_id: string;
  selected_option?: number | null;
  boolean_answer?: boolean | null;
  text_answer?: string | null;
}

export interface QuestionResult {
  question_id: string;
  position: number;
  type: QuestionType;
  question: string;
  options: string[];
  topic: string;
  your_answer: string | null;
  correct_answer: string;
  is_correct: boolean | null; // null = unanswered
  points: number;
  max_points: number;
  graded_by: "auto" | "model" | "unanswered";
  feedback: string | null;
  explanation: string;
  source: { document_id: string; filename: string; page_number: number | null };
}

export interface AttemptResult {
  attempt_id: string;
  quiz_id: string;
  points: number;
  max_points: number;
  score_percent: number;
  graded_by_model: boolean;
  grading_note: string | null;
  results: QuestionResult[];
}

// ---- Flashcards ----
export type CardDifficulty = "easy" | "medium" | "difficult";

export interface Flashcard {
  id: string;
  position: number;
  front: string;
  back: string;
  topic: string;
  document_id: string;
  filename: string;
  page_number: number | null;
  difficulty: CardDifficulty | null;
  rated_at: string | null;
}

export interface Deck {
  id: string;
  title: string;
  document_ids: string[];
  created_at: string;
  cards: Flashcard[];
}
