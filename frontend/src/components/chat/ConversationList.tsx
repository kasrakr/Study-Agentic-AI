import { MessageSquarePlus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ConversationSummary } from "@/types/api";

export default function ConversationList({ conversations, activeId, onOpen, onDelete, onNew }: {
  conversations: ConversationSummary[]; activeId: string | null;
  onOpen: (id: string) => void; onDelete: (id: string) => void; onNew: () => void;
}) {
  return (
    <nav aria-label="Conversations" className="flex flex-col gap-2">
      <Button variant="secondary" onClick={onNew} className="w-full justify-start">
        <MessageSquarePlus className="size-4" aria-hidden /> New conversation
      </Button>
      {conversations.length === 0 ? (
        <p className="px-1 text-xs text-muted">Your past conversations appear here.</p>
      ) : (
        <ul className="space-y-0.5">
          {conversations.map((c) => (
            <li key={c.id} className={cn("group flex items-center rounded-md", c.id === activeId ? "bg-accent-soft" : "hover:bg-surface")}>
              <button type="button" onClick={() => onOpen(c.id)} aria-current={c.id === activeId ? "true" : undefined}
                      className="min-w-0 flex-1 px-2.5 py-2 text-left">
                <span className="block truncate text-sm font-medium">{c.title}</span>
                <span className="block text-xs text-muted">{timeAgo(c.updated_at)}</span>
              </button>
              <button type="button" onClick={() => onDelete(c.id)} aria-label={`Delete conversation ${c.title}`}
                      className="mr-1 rounded p-1.5 text-muted opacity-60 hover:bg-paper hover:text-danger focus-visible:opacity-100 group-hover:opacity-100">
                <Trash2 className="size-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
