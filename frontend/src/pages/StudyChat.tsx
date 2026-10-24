import { ArrowDown, ChevronDown } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ChatEmptyState, { type Starter } from "@/components/chat/ChatEmptyState";
import ChatHeader, { type SystemState } from "@/components/chat/ChatHeader";
import Composer, { type ComposerHandle } from "@/components/chat/Composer";
import ConversationList from "@/components/chat/ConversationList";
import MessageBubble from "@/components/chat/MessageBubble";
import DocumentPicker from "@/components/documents/DocumentPicker";
import Drawer from "@/components/ui/Drawer";
import { Notice } from "@/components/ui/feedback";
import { useToast } from "@/components/ui/Toast";
import { useAsync } from "@/hooks/useAsync";
import { useChat } from "@/hooks/useChat";
import { useDocuments } from "@/hooks/useDocuments";
import { api } from "@/lib/api";
import { errorMessage, plural } from "@/lib/format";

const NEAR_BOTTOM_PX = 120;

export default function StudyChat() {
  const docs = useDocuments();
  const conversations = useAsync((signal) => api.listConversations(signal));
  const chat = useChat(conversations.reload);
  const toast = useToast();
  const [scope, setScope] = useState<string[]>([]); // empty = search every indexed document
  const [params, setParams] = useSearchParams();
  const [actionError, setActionError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showJump, setShowJump] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const composer = useRef<ComposerHandle>(null);
  const openedFromUrl = useRef(false);

  // Deep link from the dashboard: /chat?c=<conversation id>
  const { open } = chat;
  useEffect(() => {
    const id = params.get("c");
    if (id && !openedFromUrl.current) {
      openedFromUrl.current = true;
      stickToBottom.current = true;
      void open(id);
      setParams({}, { replace: true });
    }
  }, [params, open, setParams]);

  // Follow new content only while the student is already at the bottom, so reading earlier answers is never interrupted.
  const last = chat.messages.at(-1);
  const followKey = `${chat.messages.length}:${last?.content.length ?? 0}:${last?.steps.length ?? 0}:${last?.status ?? ""}`;
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    if (stickToBottom.current) el.scrollTop = el.scrollHeight;
    else setShowJump(true);
  }, [followKey]);

  const onScroll = useCallback(() => {
    const el = scroller.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
    stickToBottom.current = near;
    if (near) setShowJump(false);
  }, []);

  function jumpToLatest() {
    const el = scroller.current;
    if (!el) return;
    stickToBottom.current = true;
    setShowJump(false);
    if (typeof el.scrollTo === "function") el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    else el.scrollTop = el.scrollHeight;
  }

  const send = useCallback((question: string) => {
    stickToBottom.current = true;
    setShowJump(false);
    void chat.send(question, scope);
  }, [chat, scope]);

  function pick(starter: Starter) {
    if (starter.mode === "send") send(starter.prompt);
    else composer.current?.fill(starter.prompt);
  }

  const indexedCount = docs.indexed.length;
  const scopeLabel = useMemo(
    () => (scope.length === 0 ? `Searching all ${plural(indexedCount, "document")}` : `Searching ${plural(scope.length, "selected document")}`),
    [scope, indexedCount],
  );
  const systemState: SystemState = docs.status === "loading" ? "loading" : docs.status === "error" ? "unreachable" : "ready";

  async function removeConversation(id: string) {
    setActionError(null);
    try {
      await api.deleteConversation(id);
      if (id === chat.conversationId) chat.reset();
      conversations.reload();
      toast.push("Conversation deleted.", "success");
    } catch (err) {
      setActionError(errorMessage(err));
    }
  }

  const list = (
    <ConversationList
      conversations={conversations.data?.conversations ?? []} activeId={chat.conversationId}
      loading={conversations.status === "loading"} disabled={chat.busy}
      onOpen={(id) => { setDrawerOpen(false); stickToBottom.current = true; void chat.open(id); }}
      onDelete={removeConversation}
      onNew={() => { setDrawerOpen(false); chat.reset(); }}
    />
  );

  return (
    <div className="flex h-full min-h-0 flex-1">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-line p-4 lg:flex">
        <h2 className="mb-3 px-1 text-xs font-semibold uppercase tracking-[0.08em] text-faint">Conversations</h2>
        {list}
      </aside>
      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="Conversations">{list}</Drawer>

      <section className="flex min-h-0 min-w-0 flex-1 flex-col" aria-label="Study chat">
        <ChatHeader
          state={systemState} indexedCount={indexedCount} busy={chat.busy}
          onOpenConversations={() => setDrawerOpen(true)} onNew={chat.reset} newDisabled={chat.busy || chat.messages.length === 0}
        />

        <div className="border-b border-line px-3 py-2 sm:px-5">
          <details className="group">
            <summary className="flex w-fit max-w-full cursor-pointer list-none items-center gap-2 rounded-full border border-line bg-hover px-3 py-1.5 text-xs text-muted transition-colors hover:border-line-strong hover:text-ink [&::-webkit-details-marker]:hidden">
              <ChevronDown className="size-3.5 shrink-0 transition-transform duration-200 group-open:rotate-180" aria-hidden />
              <span className="truncate">{docs.status === "loading" ? "Loading documents…" : scopeLabel}</span>
            </summary>
            <div className="mt-3 max-w-xl animate-fade-in pb-1">
              <DocumentPicker documents={docs.indexed} selected={scope} onChange={setScope} legend="Limit to these documents (none selected = all)" />
              <p className="mt-2 text-xs text-faint">Answers come from your uploaded documents first. The web is searched only if they don’t contain enough.</p>
            </div>
          </details>
        </div>

        {(chat.loadError || actionError) && <Notice tone="error" className="mx-3 mt-3 sm:mx-5">{chat.loadError ?? actionError}</Notice>}

        <div className="relative min-h-0 flex-1">
          <div ref={scroller} onScroll={onScroll} className="absolute inset-0 overflow-y-auto overscroll-contain px-3 sm:px-5" role="log" aria-live="off" aria-label="Conversation">
            <div className="mx-auto min-h-full max-w-3xl">
              {chat.messages.length === 0 ? (
                <ChatEmptyState indexedCount={indexedCount} loading={docs.status === "loading"} onPick={pick} />
              ) : (
                <div className="space-y-7 py-6">
                  {chat.messages.map((m) => <MessageBubble key={m.id} message={m} />)}
                </div>
              )}
            </div>
          </div>

          {showJump && (
            <button
              type="button" onClick={jumpToLatest} aria-label="Jump to the latest message" data-tip="Jump to latest"
              className="tip glass-strong absolute bottom-3 left-1/2 grid size-9 -translate-x-1/2 place-items-center rounded-full text-ink transition-transform hover:-translate-y-0.5 active:scale-95 animate-fade-in"
            >
              <ArrowDown className="size-4" aria-hidden />
            </button>
          )}
        </div>

        <div className="px-3 pb-3 pt-2 sm:px-5 sm:pb-4">
          <div className="mx-auto max-w-3xl">
            <Composer ref={composer} busy={chat.busy} onSend={send} onStop={chat.stop} />
          </div>
        </div>
      </section>
    </div>
  );
}
