import { tr, useTranslation } from "@/i18n";
import { BookOpenCheck, Globe, Layers, ListChecks } from "lucide-react";
import { memo, useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import SourcesPanel, { sourceDomId } from "@/components/sources/SourcesPanel";
import { Badge } from "@/components/ui/Badge";
import { buttonClass } from "@/components/ui/Button";
import CopyButton from "@/components/ui/CopyButton";
import { Notice } from "@/components/ui/feedback";
import { LogoMark } from "@/components/ui/Logo";
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

function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end animate-fade-up">
      <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md border border-accent/25 bg-tint px-4 py-2.5 text-[0.95rem] leading-relaxed shadow-glass sm:max-w-[75%]">
        {content}
      </p>
    </div>
  );
}

function AssistantMessage({ message }: { message: ChatMessage }) {
  const [highlight, setHighlight] = useState<string | null>(null);
  const known = useMemo(() => new Set(message.citations.map((c) => c.marker)), [message.citations]);
  const { id } = message;
  const cite = useCallback((marker: string) => {
    setHighlight(marker);
    document.getElementById(sourceDomId(id, marker))?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [id]);

  const streaming = message.status === "streaming";
  const showOrigin = message.status === "done" && message.answerOrigin && message.steps.some((s) => s.step === "generate_answer");

  return (
    <article className="flex gap-3 animate-fade-up" aria-label={tr("Assistant answer")} aria-busy={streaming}>
      <LogoMark className="mt-0.5 size-8 rounded-[0.65rem]" />
      <div className="min-w-0 flex-1 space-y-3">
        <AgentTimeline steps={message.steps} streaming={streaming} />

        {message.content && (
          <div>
            <AnswerMarkdown text={message.content} knownMarkers={known} onCite={cite} />
            {streaming && <span className="stream-caret" aria-hidden />}
          </div>
        )}

        {showOrigin && message.answerOrigin && (
          <p className="flex flex-wrap items-center gap-2 text-xs">
            <Badge tone={ORIGIN[message.answerOrigin].tone}>
              {message.answerOrigin.includes("web") ? <Globe className="size-3" aria-hidden /> : <BookOpenCheck className="size-3" aria-hidden />}
              {tr(ORIGIN[message.answerOrigin].text)}
            </Badge>
            {message.webSearchUsed && !message.answerOrigin.includes("web") && (
              <Badge tone="warn"><Globe className="size-3" aria-hidden /> {tr("Web search was tried but its results weren’t used")}</Badge>
            )}
          </p>
        )}

        {message.limitations && message.status === "done" && (
          <Notice tone="warning" title={tr("Limitations")}>{message.limitations}</Notice>
        )}

        {message.status === "done" && <SourcesPanel messageId={message.id} citations={message.citations} highlight={highlight} />}

        {message.artifact && (
          <Link
            to={message.artifact.type === "quiz" ? `/quiz?quiz=${message.artifact.id}` : `/flashcards?deck=${message.artifact.id}`}
            className={buttonClass("primary")}
          >
            {message.artifact.type === "quiz" ? <ListChecks className="size-4" aria-hidden /> : <Layers className="size-4" aria-hidden />}
            {tr("Open")} {tr(message.artifact.type === "quiz" ? "the quiz" : "the flashcards")}
          </Link>
        )}

        {message.status === "stopped" && <p className="text-xs italic text-muted">{tr("Stopped. This reply was not saved to the conversation.")}</p>}
        {message.status === "error" && <Notice tone="error" title={tr("This answer couldn’t be completed")}>{message.error}</Notice>}

        {message.status === "done" && message.content && (
          <div className="-ml-1.5 flex items-center gap-0.5">
            <CopyButton text={message.content} label={tr("Copy answer")} />
          </div>
        )}
      </div>
    </article>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  useTranslation();
  return message.role === "user" ? <UserMessage content={message.content} /> : <AssistantMessage message={message} />;
}

// Messages are immutable and only the last one changes while streaming, so earlier ones skip re-rendering.
export default memo(MessageBubble);
