import { tr, useTranslation } from "@/i18n";
import { ChevronDown, ExternalLink, FileText, Globe } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { hostname } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Citation } from "@/types/api";

export const sourceDomId = (messageId: string, marker: string) => `src-${messageId}-${marker}`;

/** Long excerpts are clamped; the student can expand them. Nothing is added to or rewritten in the excerpt. */
function Excerpt({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 180;
  return (
    <div className="mt-1.5">
      <p className={cn("text-xs leading-relaxed text-muted", long && !open && "line-clamp-3")}>{text}</p>
      {long && (
        <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)}
                className="mt-1 inline-flex items-center gap-1 rounded text-xs font-medium text-accent transition-colors hover:text-ink">
          {tr(open ? "Show less" : "Show more")}
          <ChevronDown className={cn("size-3 transition-transform duration-200", open && "rotate-180")} aria-hidden />
        </button>
      )}
    </div>
  );
}

const linkClass = "inline-flex min-w-0 items-center gap-1 break-words text-sm font-medium text-ink underline-offset-2 transition-colors hover:text-accent hover:underline";

/** Document and web sources are listed separately and styled differently so their origin is never ambiguous. */
export default function SourcesPanel({ messageId, citations, highlight }: {
  messageId: string; citations: Citation[]; highlight: string | null;
}) {
  useTranslation();
  const docs = citations.filter((c) => c.source_type === "document");
  const web = citations.filter((c) => c.source_type === "web");
  if (citations.length === 0) return null;

  return (
    <div className={cn("grid gap-3", docs.length > 0 && web.length > 0 && "sm:grid-cols-2")} role="group" aria-label={tr("Sources")}>
      {docs.length > 0 && (
        <section aria-label={tr("Sources from your documents")} className="min-w-0">
          <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-accent">
            <FileText className="size-3.5" aria-hidden /> {tr("From your documents")}
          </h4>
          <ul className="space-y-2">
            {docs.map((c) => (
              <li key={c.marker} id={sourceDomId(messageId, c.marker)}
                  className={cn("lift rounded-xl border border-line border-s-[3px] border-s-accent bg-accent-soft px-3 py-2.5",
                    highlight === c.marker && "border-accent/60 ring-2 ring-accent/50 animate-flash")}>
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="rounded-md bg-brand px-1.5 text-[0.7rem] font-semibold leading-[1.15rem] text-white">{c.marker}</span>
                  {c.document_id ? (
                    <a href={api.documentFileUrl(c.document_id, c.page_number)} target="_blank" rel="noopener noreferrer" className={linkClass}>
                      {c.filename}
                      <ExternalLink className="size-3 shrink-0 opacity-60" aria-hidden />
                    </a>
                  ) : (
                    <span className="text-sm font-medium">{c.filename}</span>
                  )}
                  {c.page_number != null && <span className="rounded-full bg-hover px-2 text-xs text-muted">{tr("page")} {c.page_number}</span>}
                </p>
                {c.snippet && <Excerpt text={c.snippet} />}
              </li>
            ))}
          </ul>
        </section>
      )}
      {web.length > 0 && (
        <section aria-label={tr("Sources from the web")} className="min-w-0">
          <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-web">
            <Globe className="size-3.5" aria-hidden /> {tr("From the web")}
          </h4>
          <ul className="space-y-2">
            {web.map((c) => (
              <li key={c.marker} id={sourceDomId(messageId, c.marker)}
                  className={cn("lift rounded-xl border border-line border-s-[3px] border-s-web-solid bg-web-soft px-3 py-2.5",
                    highlight === c.marker && "border-web/60 ring-2 ring-web/50 animate-flash")}>
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="rounded-md bg-web-solid px-1.5 text-[0.7rem] font-semibold leading-[1.15rem] text-white">{c.marker}</span>
                  {c.url ? (
                    <a href={c.url} target="_blank" rel="noopener noreferrer" className={linkClass}>
                      {c.title}
                      <ExternalLink className="size-3 shrink-0 opacity-60" aria-hidden />
                    </a>
                  ) : (
                    <span className="text-sm font-medium">{c.title}</span>
                  )}
                </p>
                {c.url && <p className="mt-0.5 break-all text-xs text-web">{hostname(c.url)}</p>}
                {c.snippet && <Excerpt text={c.snippet} />}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
