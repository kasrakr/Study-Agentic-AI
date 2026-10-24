import { Check, ChevronRight, Globe, Loader2 } from "lucide-react";
import { totalSeconds, type StepState } from "@/lib/chatState";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";

function StepList({ steps }: { steps: StepState[] }) {
  return (
    <ol className="space-y-1">
      {steps.map((s, i) => (
        <li key={`${s.step}-${i}`} className="flex items-start gap-2 text-xs">
          {s.phase === "running" ? (
            <Loader2 className="mt-0.5 size-3.5 shrink-0 animate-spin text-accent" aria-label="in progress" />
          ) : (
            <Check className="mt-0.5 size-3.5 shrink-0 text-ok" aria-label="done" />
          )}
          <span className={cn(s.step === "web_search" && "font-medium text-violet-800")}>
            {s.label}
            {s.detail && <span className="text-muted"> — {s.detail}</span>}
            {s.durationMs != null && <span className="text-muted"> ({(s.durationMs / 1000).toFixed(1)}s)</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** Compact activity timeline. These are real backend steps, never model reasoning. */
export default function AgentTimeline({ steps, streaming }: { steps: StepState[]; streaming: boolean }) {
  if (steps.length === 0) return streaming ? <p className="text-xs text-muted" role="status">Starting…</p> : null;
  const searchedWeb = steps.some((s) => s.step === "web_search" && s.phase === "done" && !s.detail?.startsWith("skipped"));

  if (streaming) {
    return (
      <div aria-live="polite" aria-label="Agent activity" className="rounded-md bg-paper px-3 py-2">
        <StepList steps={steps} />
      </div>
    );
  }
  const seconds = totalSeconds(steps);
  return (
    <details className="group rounded-md bg-paper px-3 py-1.5">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-xs text-muted">
        <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" aria-hidden />
        Agent activity · {plural(steps.length, "step")}{seconds ? ` · ${seconds.toFixed(1)}s` : ""}
        {searchedWeb && <span className="ml-1 inline-flex items-center gap-1 text-violet-800"><Globe className="size-3" aria-hidden /> web search used</span>}
      </summary>
      <div className="pb-1.5 pt-2"><StepList steps={steps} /></div>
    </details>
  );
}
