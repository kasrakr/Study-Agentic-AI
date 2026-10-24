import { Bot, CheckCircle2, CircleMinus, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { AttemptResult, QuestionResult } from "@/types/api";

function Verdict({ r }: { r: QuestionResult }) {
  if (r.is_correct === null) return <span className="inline-flex items-center gap-1 text-muted"><CircleMinus className="size-4" aria-hidden /> Not answered</span>;
  if (r.is_correct) return <span className="inline-flex items-center gap-1 text-ok"><CheckCircle2 className="size-4" aria-hidden /> Correct</span>;
  const partial = r.points > 0;
  return <span className="inline-flex items-center gap-1 text-danger"><XCircle className="size-4" aria-hidden /> {partial ? "Partly correct" : "Incorrect"}</span>;
}

export default function QuizResults({ result, onRetry, onNew }: { result: AttemptResult; onRetry: () => void; onNew: () => void }) {
  const percent = Math.round(result.score_percent);
  return (
    <div className="space-y-5">
      <section className="glass rounded-2xl p-5" aria-labelledby="score-heading">
        <h2 id="score-heading" className="text-sm font-medium text-muted">Your score</h2>
        <p className="mt-1 text-4xl font-semibold">{percent}%</p>
        <p className="text-sm text-muted">{result.points} of {result.max_points} points</p>
        {result.grading_note && <Notice tone="info" className="mt-3"><span className="inline-flex items-center gap-1.5"><Bot className="size-4" aria-hidden />{result.grading_note}</span></Notice>}
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={onRetry}>Retake this quiz</Button>
          <Button variant="secondary" onClick={onNew}>Create a new quiz</Button>
        </div>
      </section>

      <ol className="space-y-3">
        {result.results.map((r) => (
          <li key={r.question_id} className={cn("glass rounded-2xl p-4", r.is_correct ? "border-ok/40" : r.is_correct === false ? "border-danger/40" : "")}>
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <Verdict r={r} />
              <span className="flex items-center gap-2 text-xs text-muted">
                {r.graded_by === "model" && <Badge tone="accent"><Bot className="size-3" aria-hidden /> AI-graded</Badge>}
                {r.points} / {r.max_points}
              </span>
            </div>
            <p className="mt-2 font-medium"><span className="mr-2 text-muted">{r.position}.</span>{r.question}</p>
            <dl className="mt-2 space-y-1 text-sm">
              <div className="flex gap-2"><dt className="shrink-0 text-muted">Your answer:</dt><dd>{r.your_answer ?? <em className="text-muted">none</em>}</dd></div>
              {!r.is_correct && <div className="flex gap-2"><dt className="shrink-0 text-muted">{r.type === "short_answer" ? "Model answer:" : "Correct answer:"}</dt><dd className="font-medium">{r.correct_answer}</dd></div>}
            </dl>
            {r.feedback && <p className="mt-2 rounded-xl border border-accent/20 bg-accent-soft px-3 py-2 text-sm"><span className="font-medium">Feedback:</span> {r.feedback}</p>}
            <p className="mt-2 text-sm text-ink/80">{r.explanation}</p>
            <p className="mt-2 text-xs text-muted">
              Source:{" "}
              <a href={api.documentFileUrl(r.source.document_id, r.source.page_number)} target="_blank" rel="noopener noreferrer" className="underline">
                {r.source.filename}{r.source.page_number != null && `, page ${r.source.page_number}`}
              </a>
              {" · "}Topic: {r.topic}
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}
