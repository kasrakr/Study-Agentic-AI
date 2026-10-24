import { BookOpenText, BrainCircuit, FileQuestion, Layers, ChevronDown, Sparkles, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
  { icon: BookOpenText, title: "Explain a difficult concept", prompt: "Explain a difficult concept from my study materials in simple terms." },
  { icon: FileQuestion, title: "Build an exam-style quiz", prompt: "Quiz me on the most important ideas in my documents." },
  { icon: BrainCircuit, title: "Find the key ideas", prompt: "Summarize the key ideas in my documents and explain how they connect." },
  { icon: Layers, title: "Create revision flashcards", prompt: "Create flashcards for the most important concepts in my documents." },
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
    bottomRef.current?.scrollIntoView({
      block: "end",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
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
    <div className="study-chat-layout grid gap-5 md:grid-cols-[13.5rem_minmax(0,1fr)] xl:grid-cols-[14.5rem_minmax(0,1fr)]">
      <aside className="conversation-rail">
        <div className="mb-3 hidden items-center justify-between px-1 md:flex">
          <span className="text-[10px] font-bold tracking-[0.15em] text-slate-500">YOUR CHATS</span>
          <span className="rounded-md border border-white/[0.08] px-1.5 py-0.5 text-[10px] text-slate-500">{conversations.data?.conversations.length ?? 0}</span>
        </div>
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
        <div className="mt-5 hidden border-t border-white/[0.07] pt-4 md:block">
          <p className="px-1 text-[10px] font-bold tracking-[0.13em] text-slate-600">QUICK NOTE</p>
          <p className="mt-2 px-1 text-xs leading-relaxed text-slate-500">Answers prioritize indexed documents, with citations to help you verify the details.</p>
        </div>
      </aside>

      <section className="chat-section flex min-w-0 flex-col" aria-label="Study chat">
        <header className="mb-5">
          <div className="chat-heading-row">
            <div className="min-w-0">
              <div className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.17em] text-sky-300">
                <span className="size-1.5 rounded-full bg-sky-400 shadow-[0_0_10px_rgba(56,189,248,0.75)]" aria-hidden />
                Your learning workspace
              </div>
              <h1 className="chat-heading font-display font-semibold">Study chat</h1>
              <p className="chat-subtitle mt-2 text-sm">
                Ask questions, explore ideas, and turn your documents into a deeper understanding.
              </p>
            </div>
            <div className="hidden shrink-0 items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.025] px-3 py-1.5 text-[11px] text-slate-400 sm:flex">
              <BookOpenText className="size-3.5 text-sky-300" aria-hidden />
              <span>{indexedCount} indexed {indexedCount === 1 ? "document" : "documents"}</span>
            </div>
          </div>
        </header>

        <details className="document-scope mb-3 px-3" open={false}>
          <summary className="flex list-none items-center gap-2 text-sm text-slate-300">
            <ChevronDown className="size-4 text-sky-300" aria-hidden />
            <span>{docs.status === "loading" ? "Loading documents…" : scopeLabel}</span>
            <span className="ml-auto text-xs text-slate-500">Sources</span>
          </summary>
          <div className="border-t border-white/[0.07] pb-3 pt-3">
            <DocumentPicker documents={docs.indexed} selected={scope} onChange={setScope} legend="Limit to these documents (none selected = all)" />
          </div>
        </details>

        {(chat.loadError || actionError) && <Notice tone="error" className="mb-3">{chat.loadError ?? actionError}</Notice>}

        <div className="conversation-stream custom-scrollbar flex-1 space-y-4" role="log" aria-live="off" aria-label="Conversation">
          {chat.messages.length === 0 ? (
            <div className="chat-empty-state">
              <div className="chat-orb" aria-hidden><Sparkles className="size-7" strokeWidth={1.6} /></div>
              <p className="mt-5 text-[10px] font-bold uppercase tracking-[0.2em] text-sky-300/90">A smarter way to study</p>
              <h2 className="chat-empty-title font-display font-semibold">What are you studying today?</h2>
              <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate-400">
                Your study companion can explain complex ideas, connect concepts, and help you prepare for your next exam.
              </p>
              {indexedCount > 0 ? (
                <div className="prompt-grid">
                  {STARTERS.map(({ icon: Icon, title, prompt }) => (
                    <button key={title} type="button" onClick={() => void chat.send(prompt, scope)} className="prompt-suggestion">
                      <Icon className="size-[18px]" strokeWidth={1.8} aria-hidden />
                      <span className="min-w-0 flex-1">{title}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="mt-5 flex flex-col items-center gap-3">
                  <p className="max-w-sm text-xs leading-relaxed text-slate-500">Upload lecture notes or a PDF to unlock document-grounded answers and page-level citations.</p>
                  <Link to="/library" className="inline-flex items-center gap-2 rounded-xl border border-blue-400/25 bg-blue-500/10 px-4 py-2.5 text-sm font-medium text-blue-100 transition hover:border-blue-300/45 hover:bg-blue-500/15">
                    <UploadCloud className="size-4" aria-hidden /> Add study materials
                  </Link>
                </div>
              )}
            </div>
          ) : (
            chat.messages.map((m) => <MessageBubble key={m.id} message={m} />)
          )}
          <div ref={bottomRef} />
        </div>

        <div className="composer-dock">
          <Composer busy={chat.busy} onSend={(q) => void chat.send(q, scope)} onStop={chat.stop} />
          <p className="mt-2 flex items-center justify-center gap-1.5 text-center composer-hint">
            <span>Enter to send</span><span className="text-slate-700">·</span><span>Shift + Enter for a new line</span>
          </p>
        </div>
      </section>
    </div>
  );
}
