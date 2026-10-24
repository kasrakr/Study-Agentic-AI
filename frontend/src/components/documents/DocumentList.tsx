import { ExternalLink, FileText, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { errorMessage, formatBytes, plural, timeAgo } from "@/lib/format";
import type { StudyDocument } from "@/types/api";

const STATUS = {
  indexed: { tone: "ok", label: "Indexed" },
  processing: { tone: "warn", label: "Processing" },
  failed: { tone: "danger", label: "Failed" },
} as const;

export default function DocumentList({ documents, onChanged }: { documents: StudyDocument[]; onChanged: () => void }) {
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function remove(id: string) {
    setBusy(id);
    setError(null);
    try {
      await api.deleteDocument(id);
      setConfirming(null);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      {error && <p role="alert" className="mb-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
        {documents.map((d) => {
          const status = STATUS[d.status];
          return (
            <li key={d.id} className="flex flex-wrap items-start gap-3 px-4 py-3">
              <FileText className="mt-0.5 size-5 shrink-0 text-muted" aria-hidden />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-medium">{d.filename}</span>
                  <Badge tone={status.tone}>{status.label}</Badge>
                </div>
                <p className="mt-0.5 text-xs text-muted">
                  {d.file_type.toUpperCase()} · {formatBytes(d.size_bytes)}
                  {d.page_count != null && ` · ${plural(d.page_count, "page")}`}
                  {d.status === "indexed" && ` · ${plural(d.chunk_count, "passage")}`} · added {timeAgo(d.uploaded_at)}
                </p>
                {d.error_message && <p className="mt-1 text-sm text-danger">{d.error_message}</p>}
              </div>
              <div className="flex items-center gap-1">
                {d.status === "indexed" && (
                  <a href={api.documentFileUrl(d.id)} target="_blank" rel="noopener noreferrer"
                     className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-muted hover:bg-paper hover:text-ink"
                     aria-label={`Open ${d.filename}`}>
                    <ExternalLink className="size-4" aria-hidden /> Open
                  </a>
                )}
                {confirming === d.id ? (
                  <>
                    <Button size="sm" variant="danger" loading={busy === d.id} onClick={() => remove(d.id)} aria-label={`Confirm delete ${d.filename}`}>
                      Delete
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirming(null)}>Cancel</Button>
                  </>
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => setConfirming(d.id)} aria-label={`Delete ${d.filename}`}>
                    <Trash2 className="size-4" aria-hidden />
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs text-muted">Deleting a document also removes its indexed passages.</p>
    </div>
  );
}
