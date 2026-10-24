import { ChevronDown, Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import Composer from "@/components/chat/Composer";
import ConversationList from "@/components/chat/ConversationList";
import MessageBubble from "@/components/chat/MessageBubble";
import DocumentPicker from "@/components/documents/DocumentPicker";
import { Notice } from "@/components/ui/feedback";
import { useAsync } from "@/hooks/useAsync";
import { useChat } from "@/hooks/useChat";
import { useDocuments } from "@/hooks/useDocuments";
import { api } from "@/lib/api";
import { errorMessage, plural } from "@/lib/format";

const STARTERS = [
  "Summarize the key ideas in my documents",
  "Explain the hardest concept in my notes in simple terms",
  "Quiz me on my documents",
];

export default function StudyChat() {
  const docs = useDocuments();
  const conversations = useAsync((signal) => api.listConversations(signal));
  const chat = useChat(conversations.reload);
  const [scope, setScope] = useState<string[]>([]); // empty = search every indexed document
  const [params, setParams] = useSearchParams();
  const [actionError, setActionError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const openedFromUrl = useRef(false);

  // Deep link from the dashboard: /chat?c=<conversation id>
  const { open } = chat;
  useEffect(() => {
    const id = params.get("c");
    if (id && !openedFromUrl.current) {
      openedFromUrl.current = true;
      void open(id);
      setParams({}, { replace: true });
    }
  }, [params, open, setParams]);

  const lastLength = chat.messages.at(-1)?.content.length ?? 0;
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [chat.messages.length, lastLength]);

  const indexedCount = docs.indexed.length;
  const scopeLabel = useMemo(
    () => (scope.length === 0 ? `Searching all ${plural(indexedCount, "document")}` : `Searching ${plural(scope.length, "selected document")}`),
    [scope, indexedCount],
  );

  async function removeConversation(id: string) {
    setActionError(null);
    try {
      await api.deleteConversation(id);
      if (id === chat.conversationId) chat.reset();
      conversations.reload();
    } catch (err) {
      setActionError(errorMessage(err));
    }
  }

  return (
    <div className="grid gap-6 md:grid-cols-[15rem_1fr]">
      <aside>
        <details className="md:hidden" open={false}>
          <summary className="cursor-pointer rounded-md border border-line bg-surface px-3 py-2 text-sm font-medium">Conversations</summary>
          <div className="mt-2">
            <ConversationList conversations={conversations.data?.conversations ?? []} activeId={chat.conversationId}
              onOpen={chat.open} onDelete={removeConversation} onNew={chat.reset} />
          </div>
        </details>
        <div className="hidden md:block">
          <ConversationList conversations={conversations.data?.conversations ?? []} activeId={chat.conversationId}
            onOpen={chat.open} onDelete={removeConversation} onNew={chat.reset} />
        </div>
      </aside>

      <section className="flex min-h-[70vh] min-w-0 flex-col" aria-label="Study chat">
        <h1 className="font-display text-3xl font-semibold tracking-tight">Study chat</h1>
        <p className="mt-1 text-sm text-muted">
          Answers come from your uploaded documents first. The web is searched only if they don’t contain enough.
        </p>

        <details className="mt-3 rounded-lg border border-line bg-surface px-3 py-2">
          <summary className="flex cursor-pointer list-none items-center gap-2 text-sm">
            <ChevronDown className="size-4" aria-hidden /> {docs.status === "loading" ? "Loading documents…" : scopeLabel}
          </summary>
          <div className="mt-3">
            <DocumentPicker documents={docs.indexed} selected={scope} onChange={setScope} legend="Limit to these documents (none selected = all)" />
          </div>
        </details>

        {(chat.loadError || actionError) && <Notice tone="error" className="mt-3">{chat.loadError ?? actionError}</Notice>}

        <div className="mt-4 flex-1 space-y-4" role="log" aria-live="off" aria-label="Conversation">
          {chat.messages.length === 0 ? (
            <div className="rounded-lg border border-dashed border-line bg-surface px-5 py-8 text-center">
              <Sparkles className="mx-auto size-7 text-accent" aria-hidden />
              <h2 className="mt-2 font-display text-lg font-semibold">Ask anything about your materials</h2>
              <p className="mx-auto mt-1 max-w-md text-sm text-muted">
                {indexedCount === 0 ? "You haven’t indexed any documents yet. Upload some in the Library for page-level citations." : "Try one of these, or type your own question."}
              </p>
              {indexedCount > 0 && (
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  {STARTERS.map((s) => (
                    <button key={s} type="button" onClick={() => void chat.send(s, scope)}
                            className="rounded-full border border-line px-3 py-1.5 text-sm hover:border-accent hover:bg-accent-soft">
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            chat.messages.map((m) => <MessageBubble key={m.id} message={m} />)
          )}
          <div ref={bottomRef} />
        </div>

        <div className="sticky bottom-0 mt-4 bg-paper pb-2 pt-2">
          <Composer busy={chat.busy} onSend={(q) => void chat.send(q, scope)} onStop={chat.stop} />
          <p className="mt-1.5 text-center text-xs text-muted">Answers can contain mistakes. Check the cited sources.</p>
        </div>
      </section>
    </div>
  );
}
