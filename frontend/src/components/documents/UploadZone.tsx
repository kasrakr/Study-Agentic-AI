import { CheckCircle2, CircleAlert, CopyCheck, Loader2, UploadCloud } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { uploadWithProgress } from "@/lib/api";
import { errorMessage, formatBytes } from "@/lib/format";
import { cn } from "@/lib/utils";

const ACCEPT = ".pdf,.txt,.md,.markdown";
const EXTENSIONS = ACCEPT.split(",");

type Phase = "uploading" | "indexing" | "done" | "duplicate" | "error";
interface Item {
  id: number;
  name: string;
  size: number;
  phase: Phase;
  progress: number;
  message?: string;
}

let nextId = 1;

export default function UploadZone({ onUploaded }: { onUploaded: () => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const patch = (id: number, change: Partial<Item>) =>
    setItems((list) => list.map((i) => (i.id === id ? { ...i, ...change } : i)));

  async function handleFiles(files: File[]) {
    const queued: Item[] = files.map((f) => ({ id: nextId++, name: f.name, size: f.size, phase: "uploading", progress: 0 }));
    setItems((list) => [...queued, ...list].slice(0, 8));
    for (const [n, file] of files.entries()) {
      const item = queued[n];
      if (!EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext))) {
        patch(item.id, { phase: "error", message: "Unsupported file type. Upload a PDF, TXT or Markdown file." });
        continue;
      }
      try {
        const result = await uploadWithProgress(file, (fraction) =>
          patch(item.id, { progress: fraction, phase: fraction >= 1 ? "indexing" : "uploading" }),
        );
        patch(item.id, result.duplicate
          ? { phase: "duplicate", progress: 1, message: "This exact file is already in your library." }
          : { phase: "done", progress: 1 });
        onUploaded();
      } catch (err) {
        patch(item.id, { phase: "error", message: errorMessage(err) });
        onUploaded(); // a failed document is still listed, with its reason
      }
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) void handleFiles([...e.dataTransfer.files]);
  }

  return (
    <section aria-label="Upload documents">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center gap-2 rounded-lg border-2 border-dashed bg-surface px-6 py-8 text-center transition-colors",
          dragging ? "border-accent bg-accent-soft" : "border-line",
        )}
      >
        <UploadCloud className="size-8 text-muted" aria-hidden />
        <p className="text-sm">
          Drop files here or{" "}
          <button type="button" className="font-medium text-accent underline underline-offset-2" onClick={() => inputRef.current?.click()}>
            choose files
          </button>
        </p>
        <p className="text-xs text-muted">PDF, TXT or Markdown. Scanned PDFs without a text layer can’t be read.</p>
        <input
          ref={inputRef} type="file" accept={ACCEPT} multiple className="sr-only" aria-label="Choose files to upload"
          onChange={(e) => { if (e.target.files?.length) void handleFiles([...e.target.files]); e.target.value = ""; }}
        />
      </div>

      {items.length > 0 && (
        <ul className="mt-3 space-y-2" aria-live="polite">
          {items.map((i) => (
            <li key={i.id} className="rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm">
              <div className="flex items-center gap-2">
                <StatusIcon phase={i.phase} />
                <span className="min-w-0 flex-1 truncate font-medium">{i.name}</span>
                <span className="shrink-0 text-xs text-muted">
                  {i.phase === "uploading" && `Uploading ${Math.round(i.progress * 100)}%`}
                  {i.phase === "indexing" && "Indexing… (reading and embedding)"}
                  {i.phase === "done" && `Indexed · ${formatBytes(i.size)}`}
                  {i.phase === "duplicate" && "Already indexed"}
                  {i.phase === "error" && "Failed"}
                </span>
              </div>
              {(i.phase === "uploading" || i.phase === "indexing") && (
                <div
                  role="progressbar" aria-label={`Upload progress for ${i.name}`} aria-valuemin={0} aria-valuemax={100}
                  aria-valuenow={i.phase === "indexing" ? undefined : Math.round(i.progress * 100)}
                  className="mt-2 h-1.5 overflow-hidden rounded-full bg-paper"
                >
                  <div className={cn("h-full bg-accent transition-[width]", i.phase === "indexing" && "w-full animate-pulse")}
                       style={i.phase === "uploading" ? { width: `${i.progress * 100}%` } : undefined} />
                </div>
              )}
              {i.message && <p className={cn("mt-1.5 text-xs", i.phase === "error" ? "text-danger" : "text-muted")}>{i.message}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function StatusIcon({ phase }: { phase: Phase }) {
  if (phase === "done") return <CheckCircle2 className="size-4 shrink-0 text-ok" aria-hidden />;
  if (phase === "duplicate") return <CopyCheck className="size-4 shrink-0 text-muted" aria-hidden />;
  if (phase === "error") return <CircleAlert className="size-4 shrink-0 text-danger" aria-hidden />;
  return <Loader2 className="size-4 shrink-0 animate-spin text-accent" aria-hidden />;
}
