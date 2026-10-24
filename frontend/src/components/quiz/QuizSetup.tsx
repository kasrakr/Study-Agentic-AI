import { useState } from "react";
import DocumentPicker from "@/components/documents/DocumentPicker";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/feedback";
import { cn } from "@/lib/utils";
import type { QuestionType, QuizDifficulty, QuizGenerateRequest, StudyDocument } from "@/types/api";

const TYPES: { value: QuestionType; label: string; hint: string }[] = [
  { value: "multiple_choice", label: "Multiple choice", hint: "Marked automatically" },
  { value: "true_false", label: "True / false", hint: "Marked automatically" },
  { value: "short_answer", label: "Short answer", hint: "Graded by AI against a rubric" },
];
const DIFFICULTIES: QuizDifficulty[] = ["easy", "medium", "hard"];

export default function QuizSetup({ documents, initialDocIds, initialTopic, busy, error, onGenerate }: {
  documents: StudyDocument[]; initialDocIds: string[]; initialTopic: string; busy: boolean; error: string | null;
  onGenerate: (req: QuizGenerateRequest) => void;
}) {
  const [docIds, setDocIds] = useState<string[]>(initialDocIds);
  const [count, setCount] = useState(5);
  const [types, setTypes] = useState<QuestionType[]>(["multiple_choice"]);
  const [difficulty, setDifficulty] = useState<QuizDifficulty>("medium");
  const [topic, setTopic] = useState(initialTopic);

  const valid = docIds.length > 0 && types.length > 0 && count >= 1 && count <= 20;
  const toggleType = (t: QuestionType) => setTypes((cur) => (cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]));

  return (
    <form
      className="space-y-5 glass rounded-2xl p-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onGenerate({ document_ids: docIds, question_count: count, question_types: types, difficulty, topic: topic.trim() || undefined });
      }}
    >
      <DocumentPicker documents={documents} selected={docIds} onChange={setDocIds} legend="Create the quiz from" />

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="q-count" className="text-sm font-medium">Number of questions</label>
          <input id="q-count" type="number" min={1} max={20} value={count}
                 onChange={(e) => setCount(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
                 className="mt-1.5 block w-24 field" />
        </div>
        <fieldset>
          <legend className="text-sm font-medium">Difficulty</legend>
          <div className="mt-1.5 glass inline-flex overflow-hidden rounded-xl" role="radiogroup">
            {DIFFICULTIES.map((d) => (
              <label key={d} className={cn("cursor-pointer px-3.5 py-2 text-sm capitalize transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent", difficulty === d ? "bg-brand-gradient text-white" : "hover:bg-hover")}>
                <input type="radio" name="difficulty" value={d} checked={difficulty === d} onChange={() => setDifficulty(d)} className="sr-only" />
                {d}
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      <fieldset>
        <legend className="text-sm font-medium">Question types</legend>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {TYPES.map((t) => (
            <label key={t.value} className={cn("flex cursor-pointer items-start gap-2 rounded-xl border px-3 py-2 text-sm transition-colors", types.includes(t.value) ? "border-accent/60 bg-accent-soft" : "border-line hover:bg-hover")}>
              <input type="checkbox" checked={types.includes(t.value)} onChange={() => toggleType(t.value)} className="mt-0.5 size-4 accent-[var(--color-brand)]" />
              <span>{t.label}<span className="block text-xs text-muted">{t.hint}</span></span>
            </label>
          ))}
        </div>
      </fieldset>

      <div>
        <label htmlFor="q-topic" className="text-sm font-medium">Focus on a topic <span className="font-normal text-muted">(optional)</span></label>
        <input id="q-topic" value={topic} maxLength={200} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. cellular respiration"
               className="mt-1.5 block w-full field" />
      </div>

      {error && <Notice tone="error" title="Couldn’t create the quiz">{error}</Notice>}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={!valid} loading={busy}>{busy ? "Creating quiz…" : "Create quiz"}</Button>
        {busy && <span className="text-sm text-muted" role="status">This can take 10–30 seconds.</span>}
        {!busy && !valid && <span className="text-sm text-muted">Select at least one document and one question type.</span>}
      </div>
      <p className="text-xs text-muted">Questions are based only on the selected documents, not on web content.</p>
    </form>
  );
}
