import { tr, useTranslation } from "@/i18n";
import { CheckCircle2, CircleAlert, Loader2, RefreshCw, ShieldCheck, XCircle } from "lucide-react";
import { useState } from "react";
import { useAsync } from "@/hooks/useAsync";
import { API_BASE_URL, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { OpenAIHealth, ProbeResult } from "@/types/api";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line py-3 last:border-b-0">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="text-right text-sm font-medium">{children}</dd>
    </div>
  );
}

function Flag({ ok, yes, no }: { ok: boolean; yes: string; no: string }) {
  const Icon = ok ? CheckCircle2 : CircleAlert;
  return (
    <span className={cn("inline-flex items-center gap-1.5", ok ? "text-ok" : "text-warn")}>
      <Icon className="size-4" aria-hidden />
      {ok ? yes : no}
    </span>
  );
}

function ProbeLine({ name, probe }: { name: string; probe: ProbeResult }) {
  return (
    <li className="flex items-start gap-2 py-1.5 text-sm">
      {probe.ok ? (
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" aria-hidden />
      ) : (
        <XCircle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
      )}
      <span>
        <span className="font-medium">{name}</span> <span className="text-muted">({probe.model})</span>
        {probe.ok ? ` ${tr("works.")}` : ` ${tr("Failed")}: ${probe.error?.message ?? tr("unknown error")}`}
      </span>
    </li>
  );
}

function OpenAICheck() {
  const [state, setState] = useState<
    { status: "idle" } | { status: "running" } | { status: "done"; result: OpenAIHealth } | { status: "error"; message: string }
  >({ status: "idle" });

  async function run() {
    setState({ status: "running" });
    try {
      setState({ status: "done", result: await api.verifyOpenAI() });
    } catch (err) {
      setState({ status: "error", message: err instanceof Error ? err.message : "Check failed." });
    }
  }

  return (
    <section aria-labelledby="verify-heading" className="mt-10">
      <h2 id="verify-heading" className="text-lg font-semibold tracking-tight">
        {tr("Verify OpenAI access")}
      </h2>
      <p className="mt-1 max-w-prose text-sm text-muted">
        {tr("Sends one tiny embedding request and one tiny chat request using the key in")} <code>backend/.env</code>. {tr("Costs a fraction of a cent.")}
      </p>
      <button
        type="button"
        onClick={run}
        disabled={state.status === "running"}
        className="mt-4 inline-flex items-center gap-2 rounded-xl bg-brand-gradient px-4 py-2 text-sm font-medium text-white shadow-glow transition-all hover:brightness-110 active:scale-[0.97] disabled:opacity-60"
      >
        {state.status === "running" ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <ShieldCheck className="size-4" aria-hidden />}
        {state.status === "running" ? tr("Checking…") : tr("Check connection")}
      </button>

      <div aria-live="polite" className="mt-4">
        {state.status === "done" && (
          <ul className="glass rounded-2xl px-4 py-2">
            <ProbeLine name={tr("Embeddings")} probe={state.result.embedding} />
            <ProbeLine name={tr("Chat")} probe={state.result.chat} />
          </ul>
        )}
        {state.status === "error" && (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
            {state.message}
          </p>
        )}
      </div>
    </section>
  );
}

export default function SystemStatus() {
  useTranslation();
  const health = useAsync((signal) => api.health(signal));

  return (
    <div>
      <section aria-labelledby="status-heading" className="mt-8">
        <div className="flex items-center justify-between">
          <h2 id="status-heading" className="text-lg font-semibold tracking-tight">
            {tr("System status")}
          </h2>
          <button
            type="button"
            onClick={health.reload}
            className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-muted transition-colors hover:bg-hover hover:text-ink"
          >
            <RefreshCw className="size-3.5" aria-hidden />
            {tr("Refresh")}
          </button>
        </div>

        <div aria-live="polite" className="glass mt-3 rounded-2xl px-5">
          {health.status === "loading" && (
            <p className="flex items-center gap-2 py-4 text-sm text-muted">
              <Loader2 className="size-4 animate-spin" aria-hidden /> {tr("Contacting backend…")}
            </p>
          )}

          {health.status === "error" && (
            <div role="alert" className="py-4 text-sm">
              <p className="font-medium text-danger">{health.error.message}</p>
              <p className="mt-2 text-muted">
                Start it from the <code>backend</code> folder with{" "}
                <code>uvicorn app.main:create_app --factory --reload</code>. The frontend expects it at {API_BASE_URL}.
              </p>
            </div>
          )}

          {health.status === "success" && (
            <dl>
              <Row label={tr("Backend")}>
                <Flag ok yes={`${tr("Online")} (v${health.data.version})`} no="" />
              </Row>
              <Row label={tr("OpenAI API key")}>
                <Flag ok={health.data.openai_configured} yes={tr("Configured")} no={tr("Missing")} />
              </Row>
              <Row label={tr("Model endpoint")}>{health.data.openai_base_url}</Row>
              <Row label={tr("Chat model")}>{health.data.chat_model}</Row>
              <Row label={tr("Embedding model")}>{health.data.embedding_model}</Row>
              <Row label={tr("Indexed documents")}>{health.data.indexed_documents}</Row>
              <Row label={tr("Web search (Tavily)")}>
                <Flag ok={health.data.tavily_configured} yes={tr("Configured")} no={tr("Not configured")} />
              </Row>
            </dl>
          )}
        </div>
      </section>

      {health.status === "success" && <OpenAICheck />}
    </div>
  );
}
