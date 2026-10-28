import { tr, useTranslation } from "@/i18n";
import { Brain, Check, ChevronRight, FileSearch, Globe, Layers, ListChecks, Loader2, MessageSquareText, PenLine, Scale, Search, Sparkles, type LucideIcon } from "lucide-react";
import { totalSeconds, type StepState } from "@/lib/chatState";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Icons per backend step. Unknown steps fall back to a generic icon; labels always come from the backend events. */
const STEP_ICONS: Record<string, LucideIcon> = {
  classify_intent: Brain,
  retrieve_documents: FileSearch,
  grade_document_evidence: Scale,
  rewrite_query: PenLine,
  identify_missing_information: Search,
  web_search: Globe,
  grade_web_evidence: Scale,
  generate_answer: Sparkles,
  respond_smalltalk: MessageSquareText,
  generate_quiz: ListChecks,
  generate_flashcards: Layers,
};

function StepList({ steps }: { steps: StepState[] }) {
  return (
    <ol>
      {steps.map((s, i) => {
        const Icon = STEP_ICONS[s.step] ?? Sparkles;
        const running = s.phase === "running";
        const isWeb = s.step === "web_search";
        return (
          <li key={`${s.step}-${i}`} className={cn("relative flex items-start gap-2.5 pb-2.5 text-xs last:pb-0", i < steps.length - 1 && "before:absolute before:start-[0.69rem] before:top-6 before:bottom-0 before:w-px before:bg-line")}>
            <span className={cn(
              "relative z-10 grid size-[1.4rem] shrink-0 place-items-center rounded-full ring-1 ring-inset transition-colors duration-300",
              running ? "bg-accent-soft text-accent ring-accent/40" : isWeb ? "bg-web-soft text-web ring-web/30" : "bg-hover text-muted ring-line",
            )}>
              <Icon className="size-3" aria-hidden />
            </span>
            <span className={cn("min-w-0 flex-1 pt-0.5 leading-snug", running ? "text-ink" : "text-muted", isWeb && !running && "text-web")}>
              {tr(s.label)}
              {s.detail && <span className="text-faint"> — {s.detail}</span>}
              {s.durationMs != null && <span className="text-faint"> ({(s.durationMs / 1000).toFixed(1)}s)</span>}
            </span>
            {running ? (
              <Loader2 className="mt-1 size-3.5 shrink-0 animate-spin text-accent" aria-label={tr("in progress")} />
            ) : (
              <Check className="mt-1 size-3.5 shrink-0 text-ok" aria-label={tr("done")} />
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Compact activity timeline. These are real backend steps, never model reasoning. */
export default function AgentTimeline({ steps, streaming }: { steps: StepState[]; streaming: boolean }) {
  useTranslation();
  if (steps.length === 0) return streaming ? <p className="text-xs text-muted" role="status">{tr("Starting…")}</p> : null;
  const searchedWeb = steps.some((s) => s.step === "web_search" && s.phase === "done" && !s.detail?.startsWith("skipped"));

  if (streaming) {
    return (
      <div aria-live="polite" aria-label={tr("Agent activity")} className="glass rounded-xl px-3.5 py-3">
        <StepList steps={steps} />
      </div>
    );
  }
  const seconds = totalSeconds(steps);
  return (
    <details className="group glass rounded-xl px-3.5 py-2 transition-colors open:bg-surface-strong">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-md text-xs text-muted transition-colors hover:text-ink [&::-webkit-details-marker]:hidden">
        <ChevronRight className="size-3.5 transition-transform duration-200 group-open:rotate-90" aria-hidden />
        {tr("Agent activity")} · {plural(steps.length, "step")}{seconds ? ` · ${seconds.toFixed(1)}s` : ""}
        {searchedWeb && <span className="ms-1 inline-flex items-center gap-1 text-web"><Globe className="size-3" aria-hidden /> {tr("web search used")}</span>}
      </summary>
      <div className="pb-1 pt-3 animate-fade-in"><StepList steps={steps} /></div>
    </details>
  );
}
