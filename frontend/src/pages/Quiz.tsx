import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import QuizResults from "@/components/quiz/QuizResults";
import QuizSetup from "@/components/quiz/QuizSetup";
import QuizTaker from "@/components/quiz/QuizTaker";
import { Notice, PageHeader, Spinner } from "@/components/ui/feedback";
import { useDocuments } from "@/hooks/useDocuments";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/format";
import type { AttemptResult, Quiz as QuizModel, QuizAnswer, QuizGenerateRequest } from "@/types/api";

type View = { name: "setup" } | { name: "loading" } | { name: "taking"; quiz: QuizModel } | { name: "results"; quiz: QuizModel; result: AttemptResult };

export default function Quiz() {
  const docs = useDocuments();
  const [params, setParams] = useSearchParams();
  const [view, setView] = useState<View>(params.get("quiz") ? { name: "loading" } : { name: "setup" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedFromUrl = useRef(false);

  // /quiz?quiz=<id> opens an existing quiz (e.g. one created from chat).
  useEffect(() => {
    const id = params.get("quiz");
    if (!id || loadedFromUrl.current) return;
    loadedFromUrl.current = true;
    api.getQuiz(id).then(
      (quiz) => setView({ name: "taking", quiz }),
      (err) => { setError(errorMessage(err)); setView({ name: "setup" }); },
    );
  }, [params]);

  async function generate(req: QuizGenerateRequest) {
    setBusy(true);
    setError(null);
    try {
      setView({ name: "taking", quiz: await api.generateQuiz(req) });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function submit(quiz: QuizModel, answers: QuizAnswer[]) {
    setBusy(true);
    setError(null);
    try {
      setView({ name: "results", quiz, result: await api.submitQuiz(quiz.id, answers) });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const newQuiz = () => { setError(null); setParams({}, { replace: true }); setView({ name: "setup" }); };
  const prefillDocs = (params.get("docs") ?? "").split(",").filter(Boolean);

  return (
    <div>
      <PageHeader title="Quiz">Test yourself on your own material. Every question points back to the page it came from.</PageHeader>

      {view.name === "loading" && <Spinner label="Opening quiz…" />}
      {view.name === "setup" && (
        docs.status === "loading" ? <Spinner label="Loading documents…" /> :
        docs.status === "error" ? <Notice tone="error">{docs.error.message}</Notice> :
        <QuizSetup key={params.toString()} documents={docs.indexed} initialDocIds={prefillDocs.filter((id) => docs.indexed.some((d) => d.id === id))}
                   initialTopic={params.get("topic") ?? ""} busy={busy} error={error} onGenerate={generate} />
      )}
      {view.name === "taking" && (
        <QuizTaker key={`${view.quiz.id}-${view.quiz.created_at}`} quiz={view.quiz} busy={busy} error={error} onSubmit={(a) => submit(view.quiz, a)} />
      )}
      {view.name === "results" && (
        <QuizResults result={view.result} onNew={newQuiz} onRetry={() => { setError(null); setView({ name: "taking", quiz: { ...view.quiz } }); }} />
      )}
    </div>
  );
}
