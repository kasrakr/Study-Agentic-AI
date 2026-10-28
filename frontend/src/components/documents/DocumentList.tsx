import { tr, useTranslation } from "@/i18n";
import { ExternalLink, FileText, Loader2, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { errorMessage, formatBytes, plural, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { StudyDocument } from "@/types/api";

const STATUS = {
  indexed: { tone: "ok", label: "Indexed" },
  processing: { tone: "warn", label: "Processing" },
  failed: { tone: "danger", label: "Failed" },
} as const;

const TILE: Record<StudyDocument["status"], string> = {
  indexed: "bg-tint text-accent ring-accent/25",
  processing: "bg-warn-soft text-warn ring-warn/25",
  failed: "bg-danger-soft text-danger ring-danger/25",
};

export default function DocumentList({ documents, onChanged }: { documents: StudyDocument[]; onChanged: () => void }) {
  useTranslation();
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  async function remove(doc: StudyDocument) {
    setBusy(doc.id);
    setError(null);
    try {
      await api.deleteDocument(doc.id);
      setConfirming(null);
      onChanged();
      toast.push(`${tr("Delete")} ${doc.filename}.`, "success");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      {error && <p role="alert" className="mb-3 rounded-xl border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      <ul className="space-y-2.5">
        {documents.map((d) => {
          const status = STATUS[d.status];
          return (
            <li key={d.id} className="glass lift flex flex-wrap items-start gap-3.5 rounded-2xl px-4 py-3.5 animate-fade-up">
              <span className={cn("grid size-10 shrink-0 place-items-center rounded-xl ring-1 ring-inset", TILE[d.status])}>
                <FileText className="size-5" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="break-all font-medium">{d.filename}</span>
                  <Badge tone={status.tone}>
                    {d.status === "processing" && <Loader2 className="size-3 animate-spin" aria-hidden />}
                    {tr(status.label)}
                  </Badge>
                </div>
                <p className="mt-0.5 text-xs text-muted">
                  {d.file_type.toUpperCase()} · {formatBytes(d.size_bytes)}
                  {d.page_count != null && ` · ${plural(d.page_count, "page")}`}
                  {d.status === "indexed" && ` · ${plural(d.chunk_count, "passage")}`} · {tr("added")} {timeAgo(d.uploaded_at)}
                </p>
                {d.error_message && <p className="mt-1.5 text-sm text-danger">{d.error_message}</p>}
                {d.status === "failed" && <p className="mt-0.5 text-xs text-faint">{tr("To retry, delete this entry and upload the file again.")}</p>}
              </div>
              <div className="flex items-center gap-1">
                {d.status === "indexed" && (
                  <a href={api.documentFileUrl(d.id)} target="_blank" rel="noopener noreferrer"
                     className="inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-sm text-muted transition-colors hover:bg-hover hover:text-ink"
                     aria-label={`${tr("Open")} ${d.filename}`}>
                    <ExternalLink className="size-4" aria-hidden /> {tr("Open")}
                  </a>
                )}
                {confirming === d.id ? (
                  <>
                    <Button size="sm" variant="danger" loading={busy === d.id} onClick={() => remove(d)} aria-label={`${tr("Delete")} ${d.filename}`}>
                      {tr("Delete")}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirming(null)}>{tr("Cancel")}</Button>
                  </>
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => setConfirming(d.id)} aria-label={`${tr("Delete")} ${d.filename}`} className="hover:bg-danger-soft hover:text-danger">
                    <Trash2 className="size-4" aria-hidden />
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-xs text-faint">{tr("Deleting a document also removes its indexed passages.")}</p>
    </div>
  );
}
