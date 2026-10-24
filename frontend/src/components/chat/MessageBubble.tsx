import { BookOpenCheck, Globe, ListChecks, Layers } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import SourcesPanel, { sourceDomId } from "@/components/sources/SourcesPanel";
import { Badge } from "@/components/ui/Badge";
import { Notice } from "@/components/ui/feedback";
import type { ChatMessage } from "@/lib/chatState";
import type { AnswerOrigin } from "@/types/api";
import AgentTimeline from "./AgentTimeline";
import AnswerMarkdown from "./AnswerMarkdown";

const ORIGIN: Record<AnswerOrigin, { text: string; tone: "accent" | "web" | "neutral" }> = {
  documents: { text: "Answered from your documents", tone: "accent" },
  documents_and_web: { text: "Answered from your documents and the web", tone: "web" },
  web: { text: "Answered from the web only, not from your documents", tone: "web" },
  none: { text: "No source could be cited", tone: "neutral" },
};

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const [highlight, setHighlight] = useState<string | null>(null);
  const known = useMemo(() => new Set(message.citations.map((c) => c.marker)), [message.citations]);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="message-user whitespace-pre-wrap rounded-2xl rounded-br-sm px-4 py-3">{message.content}</p>
      </div>
    );
  }

  const streaming = message.status === "streaming";
  const showOrigin = message.status === "done" && message.answerOrigin && message.steps.some((s) => s.step === "generate_answer");

  function cite(marker: string) {
    setHighlight(marker);
    document.getElementById(sourceDomId(message.id, marker))?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  return (
    <article className="message-assistant rounded-2xl rounded-bl-sm border border-line bg-surface px-5 py-4" aria-label="Assistant answer" aria-busy={streaming}>
      <AgentTimeline steps={message.steps} streaming={streaming} />

      {message.content && (
        <div className="mt-3">
          <AnswerMarkdown text={message.content} knownMarkers={known} onCite={cite} />
          {streaming && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-accent align-middle" aria-hidden />}
        </div>
      )}

      {showOrigin && message.answerOrigin && (
        <p className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <Badge tone={ORIGIN[message.answerOrigin].tone}>
            {message.answerOrigin.includes("web") ? <Globe className="size-3" aria-hidden /> : <BookOpenCheck className="size-3" aria-hidden />}
            {ORIGIN[message.answerOrigin].text}
          </Badge>
          {message.webSearchUsed && !message.answerOrigin.includes("web") && (
            <Badge tone="warn"><Globe className="size-3" aria-hidden /> Web search was tried but its results weren’t used</Badge>
          )}
        </p>
      )}

      {message.limitations && message.status === "done" && (
        <Notice tone="warning" title="Limitations" className="mt-3">{message.limitations}</Notice>
      )}

      {message.status === "done" && <SourcesPanel messageId={message.id} citations={message.citations} highlight={highlight} />}

      {message.artifact && (
        <Link
          to={message.artifact.type === "quiz" ? `/quiz?quiz=${message.artifact.id}` : `/flashcards?deck=${message.artifact.id}`}
          className="mt-3 inline-flex items-center gap-2 rounded-md bg-accent px-3.5 py-2 text-sm font-medium text-white hover:bg-accent/90"
        >
          {message.artifact.type === "quiz" ? <ListChecks className="size-4" aria-hidden /> : <Layers className="size-4" aria-hidden />}
          Open {message.artifact.type === "quiz" ? "the quiz" : "the flashcards"}
        </Link>
      )}

      {message.status === "stopped" && <p className="mt-2 text-xs italic text-muted">Stopped. This reply was not saved to the conversation.</p>}
      {message.status === "error" && <Notice tone="error" title="This answer couldn’t be completed" className="mt-3">{message.error}</Notice>}
    </article>
  );
}
