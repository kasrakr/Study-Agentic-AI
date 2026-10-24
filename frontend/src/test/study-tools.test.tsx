import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DocumentList from "@/components/documents/DocumentList";
import UploadZone from "@/components/documents/UploadZone";
import FlashcardViewer from "@/components/flashcards/FlashcardViewer";
import QuizResults from "@/components/quiz/QuizResults";
import QuizTaker, { toAnswers } from "@/components/quiz/QuizTaker";
import Dashboard from "@/pages/Dashboard";
import Quiz from "@/pages/Quiz";
import type { AttemptResult, Deck, Flashcard, Progress, Quiz as QuizModel, StudyDocument } from "@/types/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    uploadWithProgress: vi.fn(),
    api: { ...actual.api, deleteDocument: vi.fn(), rateCard: vi.fn(), progress: vi.fn(), health: vi.fn(), listDocuments: vi.fn(),
           generateQuiz: vi.fn(), submitQuiz: vi.fn(), getQuiz: vi.fn() },
  };
});
import { ApiError, api, uploadWithProgress } from "@/lib/api";

const document = (over: Partial<StudyDocument> = {}): StudyDocument => ({ id: "doc_1", filename: "bio.pdf", file_type: "pdf", size_bytes: 2048,
  page_count: 4, chunk_count: 12, status: "indexed", error_message: null, embedding_model: "m", uploaded_at: new Date().toISOString(), indexed_at: null, ...over });

beforeEach(() => vi.clearAllMocks());

// ---------------------------------------------------------------- library

describe("UploadZone", () => {
  const file = (name: string) => new File(["x"], name, { type: "application/octet-stream" });
  const chooser = () => screen.getByLabelText("Choose files to upload") as HTMLInputElement;

  it("shows upload then indexing progress and finishes as indexed", async () => {
    let progress!: (fraction: number) => void;
    let finish!: (v: unknown) => void;
    vi.mocked(uploadWithProgress).mockImplementation((_f, onProgress) => new Promise((res) => { progress = onProgress; onProgress(0.5); finish = (v) => res(v as never); }));
    const onUploaded = vi.fn();
    render(<UploadZone onUploaded={onUploaded} />);
    await userEvent.upload(chooser(), file("notes.pdf"));
    expect(await screen.findByText("Uploading 50%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: /notes\.pdf/ })).toHaveAttribute("aria-valuenow", "50");
    progress(1); // fully sent; the server is now extracting, embedding and indexing
    expect(await screen.findByText(/Indexing…/)).toBeInTheDocument();
    finish({ document: document(), duplicate: false });
    expect(await screen.findByText(/^Indexed/)).toBeInTheDocument();
    expect(onUploaded).toHaveBeenCalled();
  });

  it("rejects unsupported types locally without calling the server", async () => {
    render(<UploadZone onUploaded={vi.fn()} />);
    await userEvent.upload(chooser(), file("virus.exe"), { applyAccept: false });
    expect(await screen.findByText(/Unsupported file type/)).toBeInTheDocument();
    expect(uploadWithProgress).not.toHaveBeenCalled();
  });

  it("reports duplicates and server-side failures with the server's reason", async () => {
    vi.mocked(uploadWithProgress)
      .mockResolvedValueOnce({ document: document(), duplicate: true })
      .mockRejectedValueOnce(new ApiError("No extractable text was found. The PDF may be scanned images; OCR is not supported.", 422, "document_unreadable"));
    render(<UploadZone onUploaded={vi.fn()} />);
    await userEvent.upload(chooser(), [file("a.pdf"), file("scan.pdf")]);
    expect(await screen.findByText("Already indexed")).toBeInTheDocument();
    expect(await screen.findByText(/may be scanned images/)).toBeInTheDocument();
  });
});

describe("DocumentList", () => {
  it("shows status, metadata and the processing error, and deletes only after confirmation", async () => {
    vi.mocked(api.deleteDocument).mockResolvedValue({ id: "doc_1", deleted: true });
    const onChanged = vi.fn();
    render(<DocumentList documents={[document(), document({ id: "doc_2", filename: "scan.pdf", status: "failed", error_message: "No extractable text was found." })]} onChanged={onChanged} />);
    expect(screen.getByText("Indexed")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("No extractable text was found.")).toBeInTheDocument();
    expect(screen.getByText(/4 pages · 12 passages/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Open/ })).toHaveLength(1); // failed documents have no file to open

    await userEvent.click(screen.getByRole("button", { name: "Delete bio.pdf" }));
    expect(api.deleteDocument).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirm delete bio.pdf" }));
    await waitFor(() => expect(api.deleteDocument).toHaveBeenCalledWith("doc_1"));
    expect(onChanged).toHaveBeenCalled();
  });

  it("surfaces delete failures", async () => {
    vi.mocked(api.deleteDocument).mockRejectedValue(new Error("The document is still being processed."));
    render(<DocumentList documents={[document()]} onChanged={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete bio.pdf" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm delete bio.pdf" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("still being processed");
  });
});

// ---------------------------------------------------------------- quiz

const quiz: QuizModel = { id: "q1", title: "Quiz: cells", difficulty: "medium", document_ids: ["doc_1"], question_count: 3, created_at: "2026-01-01T00:00:00Z", questions: [
  { id: "a", position: 1, type: "multiple_choice", question: "Which organelle makes ATP?", options: ["Ribosome", "Mitochondria", "Nucleus", "Golgi"], topic: "Energy" },
  { id: "b", position: 2, type: "true_false", question: "Ribosomes make ATP.", options: ["True", "False"], topic: "Energy" },
  { id: "c", position: 3, type: "short_answer", question: "Explain respiration.", options: [], topic: "Respiration" }] };

describe("QuizTaker", () => {
  it("collects each question type into the right answer payload, skipping unanswered ones", async () => {
    const onSubmit = vi.fn();
    render(<QuizTaker quiz={quiz} busy={false} error={null} onSubmit={onSubmit} />);
    expect(screen.getByText("0 of 3 answered · medium")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Mitochondria" }));
    await userEvent.click(screen.getByRole("radio", { name: "False" }));
    expect(screen.getByText(/1 unanswered will score 0/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Your answer to question 3"), "  Cells make ATP.  ");
    await userEvent.click(screen.getByRole("button", { name: "Submit answers" }));
    expect(onSubmit).toHaveBeenCalledWith([
      { question_id: "a", selected_option: 1 }, { question_id: "b", boolean_answer: false }, { question_id: "c", text_answer: "Cells make ATP." }]);
  });

  it("omits blank answers", () => {
    expect(toAnswers(quiz, { c: { text: "   " }, a: { selected: 0 } })).toEqual([{ question_id: "a", selected_option: 0 }]);
  });
});

const result: AttemptResult = { attempt_id: "t1", quiz_id: "q1", points: 1.5, max_points: 3, score_percent: 50, graded_by_model: true,
  grading_note: "Short-answer questions were graded by an AI model against a rubric.", results: [
  { question_id: "a", position: 1, type: "multiple_choice", question: "Which organelle makes ATP?", options: [], topic: "Energy", your_answer: "Mitochondria", correct_answer: "Mitochondria",
    is_correct: true, points: 1, max_points: 1, graded_by: "auto", feedback: null, explanation: "They make ATP.", source: { document_id: "doc_1", filename: "bio.pdf", page_number: 2 } },
  { question_id: "b", position: 2, type: "true_false", question: "Ribosomes make ATP.", options: [], topic: "Energy", your_answer: null, correct_answer: "False",
    is_correct: null, points: 0, max_points: 1, graded_by: "unanswered", feedback: null, explanation: "No.", source: { document_id: "doc_1", filename: "bio.pdf", page_number: null } },
  { question_id: "c", position: 3, type: "short_answer", question: "Explain respiration.", options: [], topic: "Respiration", your_answer: "Cells make ATP.", correct_answer: "Respiration makes ATP from glucose.",
    is_correct: false, points: 0.5, max_points: 1, graded_by: "model", feedback: "You missed glucose.", explanation: "Glucose is oxidised.", source: { document_id: "doc_1", filename: "bio.pdf", page_number: 3 } }] };

describe("QuizResults", () => {
  it("states every outcome in words, marks AI grading, and links sources to the page", () => {
    render(<QuizResults result={result} onRetry={vi.fn()} onNew={vi.fn()} />);
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText(/graded by an AI model/)).toBeInTheDocument();
    expect(screen.getByText("Correct")).toBeInTheDocument();
    expect(screen.getByText("Not answered")).toBeInTheDocument();
    expect(screen.getByText("Partly correct")).toBeInTheDocument(); // not colour alone
    expect(screen.getByText("AI-graded")).toBeInTheDocument();
    expect(screen.getByText(/You missed glucose/)).toBeInTheDocument();
    expect(screen.getByText("Respiration makes ATP from glucose.")).toBeInTheDocument(); // model answer shown for the miss
    const link = screen.getByRole("link", { name: "bio.pdf, page 3" });
    expect(link).toHaveAttribute("href", expect.stringMatching(/\/doc_1\/file#page=3$/));
  });
});

describe("Quiz page flow", () => {
  it("creates a quiz, takes it and shows the graded result", async () => {
    vi.mocked(api.listDocuments).mockResolvedValue({ documents: [document()], total: 1 });
    vi.mocked(api.generateQuiz).mockResolvedValue(quiz);
    vi.mocked(api.submitQuiz).mockResolvedValue(result);
    render(<MemoryRouter><Quiz /></MemoryRouter>);
    expect(await screen.findByRole("button", { name: "Create quiz" })).toBeDisabled(); // nothing selected yet
    await userEvent.click(await screen.findByRole("checkbox", { name: /bio\.pdf/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /True \/ false/ }));
    await userEvent.click(screen.getByRole("radio", { name: "hard" }));
    await userEvent.click(screen.getByRole("button", { name: "Create quiz" }));
    expect(api.generateQuiz).toHaveBeenCalledWith({ document_ids: ["doc_1"], question_count: 5, question_types: ["multiple_choice", "true_false"], difficulty: "hard", topic: undefined });

    await userEvent.click(await screen.findByRole("button", { name: "Submit answers" }));
    expect(api.submitQuiz).toHaveBeenCalledWith("q1", []);
    expect(await screen.findByText("50%")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retake this quiz" }));
    expect(await screen.findByText("0 of 3 answered · medium")).toBeInTheDocument(); // fresh answers
  });

  it("shows a generation error without losing the form", async () => {
    vi.mocked(api.listDocuments).mockResolvedValue({ documents: [document()], total: 1 });
    vi.mocked(api.generateQuiz).mockRejectedValue(new ApiError("The model did not produce any valid questions. Please try again.", 502, "quiz_generation_failed"));
    render(<MemoryRouter><Quiz /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("checkbox", { name: /bio\.pdf/ }));
    await userEvent.click(screen.getByRole("button", { name: "Create quiz" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("did not produce any valid questions");
    expect(screen.getByRole("button", { name: "Create quiz" })).toBeEnabled();
  });

  it("opens a quiz created from chat via ?quiz=", async () => {
    vi.mocked(api.getQuiz).mockResolvedValue(quiz);
    render(<MemoryRouter initialEntries={["/quiz?quiz=q1"]}><Quiz /></MemoryRouter>);
    expect(await screen.findByText("Quiz: cells")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- flashcards

const card = (n: number, over: Partial<Flashcard> = {}): Flashcard => ({ id: `c${n}`, position: n, front: `Front ${n}`, back: `Back ${n}`, topic: "Cells",
  document_id: "doc_1", filename: "bio.pdf", page_number: n, difficulty: null, rated_at: null, ...over });
const deck: Deck = { id: "d1", title: "Flashcards", document_ids: ["doc_1"], created_at: "", cards: [card(1), card(2)] };

describe("FlashcardViewer", () => {
  it("reveals, rates (persisting), navigates by button and keyboard, and summarises the deck", async () => {
    vi.mocked(api.rateCard).mockImplementation(async (id, difficulty) => ({ ...card(Number(id.slice(1))), difficulty, rated_at: "now" }));
    render(<FlashcardViewer deck={deck} onNewDeck={vi.fn()} />);
    expect(screen.getByText("Front 1")).toBeInTheDocument();
    expect(screen.queryByText("Back 1")).toBeNull();
    expect(screen.queryByRole("group", { name: /How hard/ })).toBeNull(); // rating only after seeing the answer

    await userEvent.click(screen.getByRole("button", { name: "Reveal answer" }));
    expect(screen.getByText("Back 1")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Difficult" }));
    expect(api.rateCard).toHaveBeenCalledWith("c1", "difficult");
    await waitFor(() => expect(screen.getByRole("button", { name: "Difficult" })).toHaveAttribute("aria-pressed", "true"));

    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByText("Card 2 of 2 · Flashcards")).toBeInTheDocument();
    await userEvent.keyboard("{ArrowLeft}");
    expect(screen.getByText("Card 1 of 2 · Flashcards")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await userEvent.click(screen.getByRole("button", { name: "Finish" }));

    expect(screen.getByText("Deck complete")).toBeInTheDocument();
    expect(screen.getByText(/0 easy · 0 medium · 1 difficult · 1 not rated/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Only difficult \(1\)/ }));
    expect(screen.getByText("Card 1 of 1 · Flashcards")).toBeInTheDocument();
    expect(screen.getByText("Front 1")).toBeInTheDocument();
  });

  it("reports a failed rating and links the source page", async () => {
    vi.mocked(api.rateCard).mockRejectedValue(new Error("Flashcard not found."));
    render(<FlashcardViewer deck={deck} onNewDeck={vi.fn()} />);
    expect(screen.getByRole("link", { name: "bio.pdf, page 1" })).toHaveAttribute("href", expect.stringContaining("#page=1"));
    await userEvent.click(screen.getByRole("button", { name: "Reveal answer" }));
    await userEvent.click(screen.getByRole("button", { name: "Easy" }));
    expect(await screen.findByText("Flashcard not found.")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- dashboard

const progress = (over: Partial<Progress> = {}): Progress => ({ indexed_documents: 2,
  quiz: { attempts: 2, average_score_percent: 62.5, best_score_percent: 75, recent: [
    { attempt_id: "t1", quiz_id: "q1", quiz_title: "Quiz: cells", score_percent: 75, points: 3, max_points: 4, graded_by_model: false, submitted_at: new Date().toISOString() }] },
  flashcards: { decks: 1, rated: 3, easy: 1, medium: 0, difficult: 2 },
  weak_topics: [{ topic: "Cell respiration", data_points: 3, incorrect_answers: 2, difficult_cards: 0, weak_share: 0.67, documents: [{ document_id: "doc_1", filename: "bio.pdf" }] }],
  weak_topics_method: "A topic is flagged when you have at least 2 results.", weak_topics_note: null, suggestions: [],
  recent_activity: [{ type: "chat", title: "What is ATP?", at: new Date().toISOString(), ref_id: "c7" }, { type: "quiz", title: "Quiz: cells: 75%", at: new Date().toISOString(), ref_id: "q1" }], ...over });

describe("Dashboard", () => {
  beforeEach(() => vi.mocked(api.health).mockResolvedValue({ status: "ok", version: "0.1.0", openai_configured: true, tavily_configured: false,
    openai_base_url: "https://api.gapgpt.app/v1", chat_model: "m", embedding_model: "e", indexed_documents: 2 }));

  it("shows stats, recent scores, suggested topics with a practice link, and activity links", async () => {
    vi.mocked(api.progress).mockResolvedValue(progress());
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByText("63%")).toBeInTheDocument(); // 62.5 rounded
    expect(screen.getByRole("img", { name: "75 percent" })).toBeInTheDocument();
    expect(screen.getByText("Cell respiration")).toBeInTheDocument();
    expect(screen.getByText(/2 incorrect answers, 0 difficult cards, out of 3 results/)).toBeInTheDocument();
    const practice = screen.getByRole("link", { name: /Practice this topic/ });
    expect(practice).toHaveAttribute("href", "/quiz?topic=Cell%20respiration&docs=doc_1");
    expect(screen.getByText("How are these chosen?")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /What is ATP\?/ })).toHaveAttribute("href", "/chat?c=c7");
    expect(screen.getByRole("link", { name: /Generate a quiz/ })).toHaveAttribute("href", "/quiz");
  });

  it("makes no claims when there is no data and points to the first step", async () => {
    vi.mocked(api.progress).mockResolvedValue(progress({ indexed_documents: 0, quiz: { attempts: 0, average_score_percent: null, best_score_percent: null, recent: [] },
      flashcards: { decks: 0, rated: 0, easy: 0, medium: 0, difficult: 0 }, weak_topics: [], weak_topics_note: "No quiz answers or rated flashcards yet, so there is nothing to base weak topics on.", recent_activity: [] }));
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByRole("link", { name: /Upload your first document/ })).toHaveAttribute("href", "/library");
    expect(screen.getByText(/nothing to base weak topics on/)).toBeInTheDocument();
    expect(screen.getByText("No quizzes taken yet.")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("explains how to start the backend when it is unreachable", async () => {
    vi.mocked(api.progress).mockRejectedValue(new ApiError("Cannot reach the backend at http://localhost:8000. Is it running?", 0, "network_error"));
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/Cannot reach the backend/)).toBeInTheDocument();
    expect(alert).toHaveTextContent("uvicorn app.main:create_app");
  });
});
