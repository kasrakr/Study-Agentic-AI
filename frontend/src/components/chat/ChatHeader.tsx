import { MessageSquarePlus, PanelLeft } from "lucide-react";
import { LogoMark } from "@/components/ui/Logo";
import { cn } from "@/lib/utils";

export type SystemState = "loading" | "ready" | "unreachable";

/**
 * The status dot reflects a real signal: whether the document list could be fetched from the backend,
 * and whether an answer is currently being generated. It never claims more than that.
 */
export default function ChatHeader({ state, indexedCount, busy, onOpenConversations, onNew, newDisabled }: {
  state: SystemState; indexedCount: number; busy: boolean;
  onOpenConversations: () => void; onNew: () => void; newDisabled: boolean;
}) {
  const label = busy
    ? "Working on an answer"
    : state === "loading" ? "Connecting to the backend…"
    : state === "unreachable" ? "Backend unreachable"
    : indexedCount === 0 ? "Ready · no documents indexed" : `Ready · ${indexedCount} ${indexedCount === 1 ? "document" : "documents"} indexed`;
  const dot = busy ? "bg-accent animate-dot" : state === "ready" ? "bg-ok" : state === "unreachable" ? "bg-danger" : "bg-faint";

  return (
    <header className="flex items-center gap-3 border-b border-line px-3 py-3 sm:px-5">
      <button
        type="button" onClick={onOpenConversations} aria-label="Open conversations" data-tip="Conversations"
        className="tip -ml-1 grid size-9 place-items-center rounded-xl text-muted transition-colors hover:bg-hover hover:text-ink lg:hidden"
      >
        <PanelLeft className="size-[1.15rem]" aria-hidden />
      </button>
      <LogoMark className="hidden sm:grid" />
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[1.05rem] font-semibold leading-tight tracking-tight">Study Agent</h1>
        <p className="truncate text-xs text-muted">Your intelligent study companion</p>
      </div>
      <p className="hidden items-center gap-2 rounded-full border border-line bg-hover px-3 py-1 text-xs text-muted md:flex" role="status">
        <span className={cn("size-1.5 rounded-full", dot)} aria-hidden />
        {label}
      </p>
      <button
        type="button" onClick={onNew} disabled={newDisabled} aria-label="Start a new conversation" data-tip="New conversation"
        className="tip grid size-9 place-items-center rounded-xl text-muted transition-colors hover:bg-hover hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 lg:hidden"
      >
        <MessageSquarePlus className="size-[1.15rem]" aria-hidden />
      </button>
    </header>
  );
}
