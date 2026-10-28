import { tr, useTranslation } from "@/i18n";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/feedback";
import { cn } from "@/lib/utils";
import type { Quiz, QuizAnswer, QuizQuestion } from "@/types/api";

type Draft = { selected?: number; bool?: boolean; text?: string };

const isAnswered = (q: QuizQuestion, d: Draft | undefined) =>
  q.type === "multiple_choice" ? d?.selected !== undefined : q.type === "true_false" ? d?.bool !== undefined : !!d?.text?.trim();

export function toAnswers(quiz: Quiz, drafts: Record<string, Draft>): QuizAnswer[] {
  return quiz.questions.filter((q) => isAnswered(q, drafts[q.id])).map((q) => {
    const d = drafts[q.id];
    if (q.type === "multiple_choice") return { question_id: q.id, selected_option: d.selected };
    if (q.type === "true_false") return { question_id: q.id, boolean_answer: d.bool };
    return { question_id: q.id, text_answer: d.text!.trim() };
  });
}

export default function QuizTaker({ quiz, busy, error, onSubmit }: {
  quiz: Quiz; busy: boolean; error: string | null; onSubmit: (answers: QuizAnswer[]) => void;
}) {
  useTranslation();
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const set = (id: string, d: Draft) => setDrafts((cur) => ({ ...cur, [id]: d }));
  const answered = quiz.questions.filter((q) => isAnswered(q, drafts[q.id])).length;
  const hasShort = quiz.questions.some((q) => q.type === "short_answer");

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(toAnswers(quiz, drafts)); }} className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-semibold">{quiz.title}</h2>
        <p className="text-sm text-muted" aria-live="polite">{answered} {tr("of")} {quiz.question_count} {tr("answered")} · {tr(quiz.difficulty)}</p>
      </div>

      <ol className="space-y-4">
        {quiz.questions.map((q) => {
          const d = drafts[q.id];
          return (
            <li key={q.id} className="glass rounded-2xl p-4">
              <fieldset>
                <legend className="font-medium"><span className="mr-2 text-muted">{q.position}.</span>{q.question}</legend>
                <p className="mt-0.5 text-xs text-muted">{q.topic}</p>
                <div className="mt-3 space-y-2">
                  {q.type === "multiple_choice" && q.options.map((opt, i) => (
                    <label key={i} className={cn("flex cursor-pointer items-start gap-2.5 rounded-xl border px-3 py-2.5 text-sm transition-colors", d?.selected === i ? "border-accent bg-accent-soft" : "border-line hover:bg-hover")}>
                      <input type="radio" name={q.id} checked={d?.selected === i} onChange={() => set(q.id, { selected: i })} className="mt-0.5 accent-[var(--color-brand)]" />
                      {opt}
                    </label>
                  ))}
                  {q.type === "true_false" && [true, false].map((v) => (
                    <label key={String(v)} className={cn("flex cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-2.5 text-sm transition-colors", d?.bool === v ? "border-accent bg-accent-soft" : "border-line hover:bg-hover")}>
                      <input type="radio" name={q.id} checked={d?.bool === v} onChange={() => set(q.id, { bool: v })} className="accent-[var(--color-brand)]" />
                      {v ? tr("True") : tr("False")}
                    </label>
                  ))}
                  {q.type === "short_answer" && (
                    <>
                      <label htmlFor={`a-${q.id}`} className="sr-only">Your answer to question {q.position}</label>
                      <textarea id={`a-${q.id}`} rows={3} maxLength={4000} value={d?.text ?? ""} onChange={(e) => set(q.id, { text: e.target.value })}
                                placeholder={tr("Write your answer in a sentence or two…")} className="w-full field text-sm" />
                    </>
                  )}
                </div>
              </fieldset>
            </li>
          );
        })}
      </ol>

      {error && <Notice tone="error" title={tr("Couldn’t submit your answers")}>{error}</Notice>}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" loading={busy}>{busy ? (hasShort ? tr("Grading…") : tr("Submitting…")) : tr("Submit answers")}</Button>
        {answered < quiz.question_count && <span className="text-sm text-muted">{quiz.question_count - answered} {tr("unanswered will score 0.")}</span>}
      </div>
    </form>
  );
}
