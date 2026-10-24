import { BookOpenText, FileText, FileUp, Layers, ListChecks, MessageSquareText, Target, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import SystemStatus from "@/components/dashboard/SystemStatus";
import { buttonClass } from "@/components/ui/Button";
import { Notice, Skeleton, Spinner } from "@/components/ui/feedback";
import { useAsync } from "@/hooks/useAsync";
import { api } from "@/lib/api";
import { plural, timeAgo } from "@/lib/format";
import type { ActivityItem, Progress } from "@/types/api";

function Stat({ label, value, hint, icon: Icon }: { label: string; value: string; hint?: string; icon: LucideIcon }) {
  return (
    <div className="glass lift rounded-2xl px-5 py-4">
      <div className="flex items-center justify-between">
        <dt className="text-sm text-muted">{label}</dt>
        <span className="grid size-8 place-items-center rounded-lg bg-tint ring-1 ring-inset ring-accent/20"><Icon className="size-4 text-accent" aria-hidden /></span>
      </div>
      <dd className="mt-2 text-3xl font-semibold tracking-tight">{value}</dd>
      <p className="mt-0.5 min-h-4 text-xs text-faint">{hint}</p>
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
        <Stat icon={FileText} label="Indexed documents" value={String(p.indexed_documents)} />
        <Stat icon={ListChecks} label="Average quiz score" value={avg == null ? "—" : `${Math.round(avg)}%`} hint={plural(p.quiz.attempts, "attempt")} />
        <Stat icon={Layers} label="Flashcards rated" value={String(p.flashcards.rated)} hint={p.flashcards.rated ? `${p.flashcards.difficult} difficult` : undefined} />
      </dl>

      <section className="mt-6" aria-label="Quick actions">
        <div className="flex flex-wrap gap-2">
          {empty ? (
            <Link to="/library" className={buttonClass("primary")}><FileUp className="size-4" aria-hidden /> Upload your first document</Link>
          ) : (
            <>
              <Link to="/chat" className={buttonClass("primary")}><MessageSquareText className="size-4" aria-hidden /> Ask a question</Link>
              <Link to="/quiz" className={buttonClass("secondary")}><ListChecks className="size-4" aria-hidden /> Generate a quiz</Link>
              <Link to="/flashcards" className={buttonClass("secondary")}><Layers className="size-4" aria-hidden /> Make flashcards</Link>
            </>
          )}
        </div>
      </section>

      <div className="mt-10 grid gap-8 lg:grid-cols-2">
        <section aria-labelledby="scores-heading">
          <h2 id="scores-heading" className="text-lg font-semibold tracking-tight">Recent quiz scores</h2>
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
                  <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-hover" role="img" aria-label={`${Math.round(a.score_percent)} percent`}>
                    <div className="h-full rounded-full bg-gradient-to-r from-brand to-cyan transition-[width] duration-500" style={{ width: `${a.score_percent}%` }} />
                  </div>
                  <p className="mt-0.5 text-xs text-muted">{timeAgo(a.submitted_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="review-heading">
          <h2 id="review-heading" className="flex items-center gap-2 text-lg font-semibold tracking-tight"><Target className="size-5 text-accent" aria-hidden /> Suggested topics to review</h2>
          {p.weak_topics.length === 0 ? (
            <p className="mt-2 text-sm text-muted">{p.weak_topics_note ?? "No weak topics detected from your results so far."}</p>
          ) : (
            <ul className="mt-3 space-y-2.5">
              {p.weak_topics.map((w) => (
                <li key={w.topic} className="glass lift rounded-2xl px-4 py-3.5">
                  <p className="font-medium">{w.topic}</p>
                  <p className="text-xs text-muted">
                    {w.incorrect_answers} incorrect answer{w.incorrect_answers === 1 ? "" : "s"}, {w.difficult_cards} difficult card{w.difficult_cards === 1 ? "" : "s"}, out of {plural(w.data_points, "result")}
                  </p>
                  {w.documents.length > 0 && (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Link to={`/quiz?topic=${encodeURIComponent(w.topic)}&docs=${w.documents.map((d) => d.document_id).join(",")}`} className={buttonClass("secondary", "sm")}>
                        Practice this topic
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

      <section className="mt-10" aria-labelledby="activity-heading">
        <h2 id="activity-heading" className="text-lg font-semibold tracking-tight">Recent activity</h2>
        {p.recent_activity.length === 0 ? (
          <p className="mt-2 text-sm text-muted">Nothing yet. Upload a document to get started.</p>
        ) : (
          <ul className="glass mt-3 divide-y divide-line overflow-hidden rounded-2xl">
            {p.recent_activity.map((a) => (
              <li key={`${a.type}-${a.ref_id}-${a.at}`}>
                <Link to={ACTIVITY_LINK[a.type](a.ref_id)} className="flex items-baseline justify-between gap-3 px-4 py-3 text-sm transition-colors hover:bg-hover">
                  <span className="min-w-0 truncate"><span className="mr-2 text-xs font-semibold uppercase tracking-[0.08em] text-accent">{ACTIVITY_VERB[a.type]}</span>{a.title}</span>
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
      <header className="mb-8 flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-gradient text-3xl font-semibold tracking-tight sm:text-[2.1rem]">Dashboard</h1>
          <p className="mt-2 inline-flex items-center gap-2 leading-relaxed text-muted">
            <BookOpenText className="size-4 shrink-0 text-accent" aria-hidden /> Your study progress at a glance.
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-0.5">
          
        </div>
      </header>

      {progress.status === "loading" && (
        <div className="space-y-3">
          <Spinner label="Loading your progress…" />
          <div className="grid gap-3 sm:grid-cols-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
        </div>
      )}
      {progress.status === "error" && (
        <Notice tone="error" title="Couldn’t load your progress">
          {progress.error.message} Check that the backend is running (<code>uvicorn app.main:create_app --factory --reload</code>).
        </Notice>
      )}
      {progress.status === "success" && <Overview p={progress.data} />}

      <details className="glass group mt-12 rounded-2xl px-4 py-3">
        <summary className="cursor-pointer rounded-lg text-sm font-medium text-muted transition-colors hover:text-ink">System status and connection check</summary>
        <div className="mt-2"><SystemStatus /></div>
      </details>
    </div>
  );
}
