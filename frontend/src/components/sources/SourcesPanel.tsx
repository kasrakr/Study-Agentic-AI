import { FileText, Globe } from "lucide-react";
import { api } from "@/lib/api";
import { hostname } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Citation } from "@/types/api";

export const sourceDomId = (messageId: string, marker: string) => `src-${messageId}-${marker}`;

/** Document and web sources are listed separately and styled differently so their origin is never ambiguous. */
export default function SourcesPanel({ messageId, citations, highlight }: {
  messageId: string; citations: Citation[]; highlight: string | null;
}) {
  const docs = citations.filter((c) => c.source_type === "document");
  const web = citations.filter((c) => c.source_type === "web");
  if (citations.length === 0) return null;

  return (
    <div className="mt-3 grid gap-3 sm:grid-cols-2" aria-label="Sources">
      {docs.length > 0 && (
        <section aria-label="Sources from your documents">
          <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-accent">
            <FileText className="size-3.5" aria-hidden /> From your documents
          </h4>
          <ul className="space-y-2">
            {docs.map((c) => (
              <li key={c.marker} id={sourceDomId(messageId, c.marker)}
                  className={cn("rounded-md border-l-4 border-accent bg-accent-soft/50 px-3 py-2 text-sm", highlight === c.marker && "ring-2 ring-accent")}>
                <p className="flex flex-wrap items-baseline gap-x-2 font-medium">
                  <span className="rounded bg-accent px-1.5 text-xs text-white">{c.marker}</span>
                  <a href={api.documentFileUrl(c.document_id!, c.page_number)} target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:underline">
                    {c.filename}
                  </a>
                  {c.page_number != null && <span className="text-xs font-normal text-muted">page {c.page_number}</span>}
                </p>
                <p className="mt-1 text-xs text-muted">{c.snippet}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
      {web.length > 0 && (
        <section aria-label="Sources from the web">
          <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-violet-800">
            <Globe className="size-3.5" aria-hidden /> From the web
          </h4>
          <ul className="space-y-2">
            {web.map((c) => (
              <li key={c.marker} id={sourceDomId(messageId, c.marker)}
                  className={cn("rounded-md border-l-4 border-violet-500 bg-violet-50/60 px-3 py-2 text-sm", highlight === c.marker && "ring-2 ring-violet-500")}>
                <p className="flex flex-wrap items-baseline gap-x-2 font-medium">
                  <span className="rounded bg-violet-700 px-1.5 text-xs text-white">{c.marker}</span>
                  <a href={c.url!} target="_blank" rel="noopener noreferrer" className="break-words underline-offset-2 hover:underline">
                    {c.title}
                  </a>
                </p>
                <p className="text-xs text-violet-800">{hostname(c.url!)}</p>
                <p className="mt-1 text-xs text-muted">{c.snippet}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
