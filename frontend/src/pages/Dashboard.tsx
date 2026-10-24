import { BookOpenText, FileUp, Layers, ListChecks, MessageSquareText, Target } from "lucide-react";
import { Link } from "react-router-dom";
import SystemStatus from "@/components/dashboard/SystemStatus";
import { Button } from "@/components/ui/Button";
import { Notice, PageHeader, Spinner } from "@/components/ui/feedback";
import { useAsync } from "@/hooks/useAsync";
import { api } from "@/lib/api";
import { plural, timeAgo } from "@/lib/format";
import type { ActivityItem, Progress } from "@/types/api";

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3.5">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-1 font-display text-2xl font-semibold">{value}</dd>
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
  );
}

const ACTIVITY_LINK: Record<ActivityItem["type"], (id: string) => string> = {
  upload: () => "/library",
  chat: (id) => `/chat?c=${id}`,
  quiz: (id) => `/quiz?quiz=${id}`,
  flashcards: (id) => `/flashcards?deck=${id}`,
};
const ACTIVITY_VERB: Record<ActivityItem["type"], string> = { upload: "Document", chat: "Chat", quiz: "Quiz", flashcards: "Flashcards" };

function Overview({ p }: { p: Progress }) {
  const avg = p.quiz.average_score_percent;
  const empty = p.indexed_documents === 0;
  return (
    <>
      <dl className="grid gap-3 sm:grid-cols-3">
        <Stat label="Indexed documents" value={String(p.indexed_documents)} />
        <Stat label="Average quiz score" value={avg == null ? "—" : `${Math.round(avg)}%`} hint={plural(p.quiz.attempts, "attempt")} />
        <Stat label="Flashcards rated" value={String(p.flashcards.rated)} hint={p.flashcards.rated ? `${p.flashcards.difficult} difficult` : undefined} />
      </dl>

      <section className="mt-6" aria-label="Quick actions">
        <div className="flex flex-wrap gap-2">
          {empty ? (
            <Link to="/library"><Button><FileUp className="size-4" aria-hidden /> Upload your first document</Button></Link>
          ) : (
            <>
              <Link to="/chat"><Button><MessageSquareText className="size-4" aria-hidden /> Ask a question</Button></Link>
              <Link to="/quiz"><Button variant="secondary"><ListChecks className="size-4" aria-hidden /> Generate a quiz</Button></Link>
              <Link to="/flashcards"><Button variant="secondary"><Layers className="size-4" aria-hidden /> Make flashcards</Button></Link>
            </>
          )}
        </div>
      </section>

      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        <section aria-labelledby="scores-heading">
          <h2 id="scores-heading" className="font-display text-xl font-semibold">Recent quiz scores</h2>
          {p.quiz.recent.length === 0 ? (
            <p className="mt-2 text-sm text-muted">No quizzes taken yet.</p>
          ) : (
            <ul className="mt-3 space-y-2.5">
              {p.quiz.recent.slice(0, 6).map((a) => (
                <li key={a.attempt_id}>
                  <div className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="truncate">{a.quiz_title}</span>
                    <span className="shrink-0 font-medium">{Math.round(a.score_percent)}%{a.graded_by_model && <span className="ml-1 text-xs font-normal text-muted" title="Includes AI-graded short answers">(AI-graded part)</span>}</span>
                  </div>
                  <div className="mt-1 h-2 overflow-hidden rounded-full bg-line" role="img" aria-label={`${Math.round(a.score_percent)} percent`}>
                    <div className="h-full bg-accent" style={{ width: `${a.score_percent}%` }} />
                  </div>
                  <p className="mt-0.5 text-xs text-muted">{timeAgo(a.submitted_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="review-heading">
          <h2 id="review-heading" className="flex items-center gap-2 font-display text-xl font-semibold"><Target className="size-5 text-accent" aria-hidden /> Suggested topics to review</h2>
          {p.weak_topics.length === 0 ? (
            <p className="mt-2 text-sm text-muted">{p.weak_topics_note ?? "No weak topics detected from your results so far."}</p>
          ) : (
            <ul className="mt-3 space-y-2.5">
              {p.weak_topics.map((w) => (
                <li key={w.topic} className="rounded-lg border border-line bg-surface px-3.5 py-3">
                  <p className="font-medium">{w.topic}</p>
                  <p className="text-xs text-muted">
                    {w.incorrect_answers} incorrect answer{w.incorrect_answers === 1 ? "" : "s"}, {w.difficult_cards} difficult card{w.difficult_cards === 1 ? "" : "s"}, out of {plural(w.data_points, "result")}
                  </p>
                  {w.documents.length > 0 && (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Link to={`/quiz?topic=${encodeURIComponent(w.topic)}&docs=${w.documents.map((d) => d.document_id).join(",")}`}>
                        <Button size="sm" variant="secondary">Practice this topic</Button>
                      </Link>
                      <span className="text-xs text-muted">in {w.documents.map((d) => d.filename).join(", ")}</span>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
          <details className="mt-3 text-xs text-muted">
            <summary className="cursor-pointer">How are these chosen?</summary>
            <p className="mt-1.5 max-w-prose">{p.weak_topics_method}</p>
          </details>
        </section>
      </div>

      <section className="mt-8" aria-labelledby="activity-heading">
        <h2 id="activity-heading" className="font-display text-xl font-semibold">Recent activity</h2>
        {p.recent_activity.length === 0 ? (
          <p className="mt-2 text-sm text-muted">Nothing yet. Upload a document to get started.</p>
        ) : (
          <ul className="mt-3 divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
            {p.recent_activity.map((a) => (
              <li key={`${a.type}-${a.ref_id}-${a.at}`}>
                <Link to={ACTIVITY_LINK[a.type](a.ref_id)} className="flex items-baseline justify-between gap-3 px-4 py-2.5 text-sm hover:bg-paper">
                  <span className="min-w-0 truncate"><span className="mr-2 text-xs font-medium uppercase tracking-wide text-muted">{ACTIVITY_VERB[a.type]}</span>{a.title}</span>
                  <span className="shrink-0 text-xs text-muted">{timeAgo(a.at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

export default function Dashboard() {
  const progress = useAsync((signal) => api.progress(signal));
  return (
    <div>
      <PageHeader title="Dashboard">
        <span className="inline-flex items-center gap-2"><BookOpenText className="size-4" aria-hidden /> Your study progress at a glance.</span>
      </PageHeader>

      {progress.status === "loading" && <Spinner label="Loading your progress…" />}
      {progress.status === "error" && (
        <Notice tone="error" title="Couldn’t load your progress">
          {progress.error.message} Check that the backend is running (<code>uvicorn app.main:create_app --factory --reload</code>).
        </Notice>
      )}
      {progress.status === "success" && <Overview p={progress.data} />}

      <details className="mt-10 rounded-lg border border-line bg-surface px-4 py-3">
        <summary className="cursor-pointer text-sm font-medium">System status and connection check</summary>
        <div className="mt-2"><SystemStatus /></div>
      </details>
    </div>
  );
}
