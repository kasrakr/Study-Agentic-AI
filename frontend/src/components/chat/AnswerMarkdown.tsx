import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { linkifyMarkers } from "@/lib/chatState";
import { cn } from "@/lib/utils";

export function CitationChip({ marker, known, onClick }: { marker: string; known: boolean; onClick: (marker: string) => void }) {
  const isWeb = marker.startsWith("W");
  return (
    <button
      type="button" onClick={() => onClick(marker)} disabled={!known}
      aria-label={`${isWeb ? "Web" : "Document"} source ${marker}`}
      className={cn(
        "mx-0.5 inline-block -translate-y-0.5 rounded px-1 align-baseline text-[0.7rem] font-semibold leading-4 text-white",
        isWeb ? "bg-violet-700 hover:bg-violet-800" : "bg-accent hover:bg-accent/80", !known && "opacity-50",
      )}
    >
      {marker}
    </button>
  );
}

/**
 * Renders the model's Markdown. Raw HTML is not rendered, and links are shown as plain text: the only links we
 * display are the verified source links in the sources panel, never URLs written by the model.
 */
export default function AnswerMarkdown({ text, knownMarkers, onCite }: {
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
          table: ({ children }) => <div className="my-2 overflow-x-auto"><table>{children}</table></div>,
        }}
      >
        {linkifyMarkers(text)}
      </ReactMarkdown>
    </div>
  );
}
