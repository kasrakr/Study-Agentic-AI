import { isValidElement, memo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import CopyButton from "@/components/ui/CopyButton";
import { linkifyMarkers } from "@/lib/chatState";
import { cn } from "@/lib/utils";

export function CitationChip({ marker, known, onClick }: { marker: string; known: boolean; onClick: (marker: string) => void }) {
  const isWeb = marker.startsWith("W");
  return (
    <button
      type="button" onClick={() => onClick(marker)} disabled={!known}
      aria-label={`${isWeb ? "Web" : "Document"} source ${marker}`}
      className={cn(
        "mx-0.5 inline-block -translate-y-0.5 rounded-md px-1.5 align-baseline text-[0.7rem] font-semibold leading-[1.15rem] text-white transition-all duration-150 active:scale-95",
        isWeb ? "bg-web-solid hover:brightness-125" : "bg-brand hover:brightness-125", !known && "opacity-50",
      )}
    >
      {marker}
    </button>
  );
}

function textOf(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children);
  return "";
}

/** Fenced code block with a language label and a copy action. */
function CodeBlock({ children }: { children: ReactNode }) {
  const code = isValidElement<{ className?: string }>(children) ? children : null;
  const language = /language-([\w+#-]+)/.exec(code?.props.className ?? "")?.[1];
  const raw = textOf(children).replace(/\n$/, "");
  return (
    <div className="code-block my-3">
      <div className="flex items-center justify-between border-b border-line bg-hover px-3 py-1">
        <span className="font-mono text-[0.7rem] uppercase tracking-wide text-faint">{language ?? "code"}</span>
        <CopyButton text={raw} label="Copy code" withLabel />
      </div>
      <pre tabIndex={0} aria-label={language ? `${language} code` : "Code"}>{children}</pre>
    </div>
  );
}

/**
 * Renders the model's Markdown. Raw HTML is not rendered, and links are shown as plain text: the only links we
 * display are the verified source links in the sources panel, never URLs written by the model.
 */
function AnswerMarkdown({ text, knownMarkers, onCite }: {
  text: string; knownMarkers: Set<string>; onCite: (marker: string) => void;
}) {
  return (
    <div className="prose-answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => (url.startsWith("cite:") ? url : "")}
        components={{
          a: ({ href, children }) =>
            href?.startsWith("cite:") ? (
              <CitationChip marker={href.slice(5)} known={knownMarkers.has(href.slice(5))} onClick={onCite} />
            ) : (
              <span>{children}</span>
            ),
          pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
          table: ({ children }) => <div className="table-wrap"><table>{children}</table></div>,
        }}
      >
        {linkifyMarkers(text)}
      </ReactMarkdown>
    </div>
  );
}

// Memoised so finished answers are not re-parsed while a later answer streams in.
export default memo(AnswerMarkdown);
