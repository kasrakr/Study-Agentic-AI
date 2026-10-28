import { tr, useTranslation } from "@/i18n";
import { MessageSquarePlus, Trash2 } from "lucide-react";
import { Skeleton } from "@/components/ui/feedback";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ConversationSummary } from "@/types/api";

export default function ConversationList({ conversations, activeId, onOpen, onDelete, onNew, loading = false, disabled = false }: {
  conversations: ConversationSummary[]; activeId: string | null;
  onOpen: (id: string) => void; onDelete: (id: string) => void; onNew: () => void;
  loading?: boolean; disabled?: boolean;
}) {
  useTranslation();
  return (
    <nav aria-label={tr("Conversations")} className="flex min-h-0 flex-col gap-3">
      <button
        type="button" onClick={onNew} disabled={disabled}
        className="glass flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium transition-all hover:border-accent/40 hover:bg-surface-strong active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <MessageSquarePlus className="size-4 text-accent" aria-hidden /> {tr("New conversation")}
      </button>

      {loading && conversations.length === 0 ? (
        <div className="space-y-2" aria-hidden>
          <Skeleton className="h-11" /><Skeleton className="h-11" /><Skeleton className="h-11" />
        </div>
      ) : conversations.length === 0 ? (
        <p className="px-1 text-xs leading-relaxed text-faint">{tr("Your past conversations appear here.")}</p>
      ) : (
        <ul className="min-h-0 space-y-0.5 overflow-y-auto pe-0.5">
          {conversations.map((c) => (
            <li key={c.id} className={cn("group relative flex items-center rounded-xl transition-colors", c.id === activeId ? "bg-accent-soft" : "hover:bg-hover")}>
              {c.id === activeId && <span aria-hidden className="absolute start-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-e-full bg-gradient-to-b from-cyan to-accent" />}
              <button type="button" onClick={() => onOpen(c.id)} aria-current={c.id === activeId ? "true" : undefined}
                      className="min-w-0 flex-1 rounded-xl px-3 py-2 text-start">
                <span className={cn("block truncate text-sm font-medium", c.id === activeId ? "text-ink" : "text-ink/90")}>{c.title}</span>
                <span className="block text-xs text-faint">{timeAgo(c.updated_at)}</span>
              </button>
              <button type="button" onClick={() => onDelete(c.id)} aria-label={`${tr("Delete conversation")} ${c.title}`}
                      className="me-1 rounded-sg p-1.5 text-muted opacity-0 transition-all hover:bg-danger-soft hover:text-danger focus-visible:opacity-100 group-hover:opacity-100 max-lg:opacity-70">
                <Trash2 className="size-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
