import { tr, useTranslation } from "@/i18n";
import { Paperclip, SendHorizontal, Square } from "lucide-react";
import { useImperativeHandle, useLayoutEffect, useRef, useState, type KeyboardEvent, type Ref } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

export interface ComposerHandle {
  /** Replace the draft and focus the input (used by prompt suggestions that need the student to finish the sentence). */
  fill: (text: string) => void;
}

const MAX_LENGTH = 4000;
const MAX_HEIGHT_PX = 176;

function Kbd({ children }: { children: string }) {
  return <kbd className="rounded-md border border-line bg-hover px-1.5 py-px font-mono text-[0.65rem] text-muted">{children}</kbd>;
}

export default function Composer({ busy, onSend, onStop, placeholder, ref }: {
  busy: boolean; onSend: (text: string) => void; onStop: () => void; placeholder?: string; ref?: Ref<ComposerHandle>;
}) {
  useTranslation();
  const [text, setText] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    fill(value: string) {
      setText(value);
      requestAnimationFrame(() => {
        const el = input.current;
        if (!el) return;
        el.focus();
        el.setSelectionRange(value.length, value.length);
      });
    },
  }), []);

  // Grow with the content up to a cap, then scroll inside the box.
  useLayoutEffect(() => {
    const el = input.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [text]);

  function submit() {
    const value = text.trim();
    if (!value || busy) return;
    onSend(value);
    setText("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  const nearLimit = text.length > MAX_LENGTH * 0.8;

  return (
    <div>
      <form
        onSubmit={(e) => { e.preventDefault(); submit(); }}
        className="glass-strong group/composer flex items-end gap-1.5 rounded-2xl p-2 shadow-lift transition-[border-color,box-shadow] duration-200 focus-within:border-accent/60 focus-within:shadow-[0_0_0_4px_rgb(59_130_246/0.14),0_22px_44px_-20px_rgb(2_6_23/0.85)]"
      >
        <Link
          to="/library" aria-label={tr("Add documents in the Library")} data-tip={tr("Add documents in the Library")}
          className="tip mb-0.5 grid size-9 shrink-0 place-items-center rounded-xl text-muted transition-colors hover:bg-hover hover:text-ink"
        >
          <Paperclip className="size-[1.1rem]" aria-hidden />
        </Link>

        <label htmlFor="composer" className="sr-only">{tr("Ask a question about your study materials")}</label>
        <textarea
          id="composer" ref={input} rows={1} value={text} maxLength={MAX_LENGTH}
          placeholder={placeholder ?? tr("Ask about your study materials…")}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          className="max-h-44 min-h-10 flex-1 resize-none bg-transparent px-1.5 py-2 text-[0.95rem] leading-relaxed text-ink outline-none placeholder:text-faint"
        />

        {nearLimit && (
          <span className={cn("mb-2.5 shrink-0 text-xs tabular-nums", text.length >= MAX_LENGTH ? "text-danger" : "text-faint")} aria-live="polite">
            {text.length}/{MAX_LENGTH}
          </span>
        )}

        {busy ? (
          <button
            type="button" onClick={onStop} aria-label={tr("Stop generating")} data-tip={tr("Stop generating")}
            className="tip mb-0.5 inline-flex h-9 shrink-0 items-center gap-2 rounded-xl border border-line-strong bg-hover px-3 text-sm font-medium transition-all hover:bg-surface-strong active:scale-95"
          >
            <Square className="size-3.5 fill-current" aria-hidden /> <span className="hidden sm:inline">{tr("Stop")}</span>
          </button>
        ) : (
          <button
            type="submit" disabled={!text.trim()} aria-label={tr("Send message")} data-tip={tr("Send (Enter)")}
            className="tip mb-0.5 inline-flex h-9 shrink-0 items-center gap-2 rounded-xl bg-brand-gradient px-3.5 text-sm font-medium text-white shadow-glow transition-all hover:brightness-110 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none disabled:active:scale-100"
          >
            <SendHorizontal className="size-4" aria-hidden /> <span className="hidden sm:inline">{tr("Send")}</span>
          </button>
        )}
      </form>

      <div className="mt-2 flex min-h-5 items-center justify-between gap-3 px-2 text-xs text-faint">
        {busy ? (
          <p className="flex items-center gap-2 text-muted" role="status">
            <span className="flex gap-0.5" aria-hidden>
              <span className="size-1 rounded-full bg-accent animate-dot" />
              <span className="size-1 rounded-full bg-accent animate-dot [animation-delay:0.15s]" />
              <span className="size-1 rounded-full bg-accent animate-dot [animation-delay:0.3s]" />
            </span>
            {tr("Generating a response…")}
          </p>
        ) : (
          <p className="hidden items-center gap-1.5 sm:flex"><Kbd>Enter</Kbd> {tr("to send")} <span aria-hidden>·</span> <Kbd>Shift</Kbd>+<Kbd>Enter</Kbd> {tr("for a new line")}</p>
        )}
        <p className="ms-auto text-end">{tr("Answers can contain mistakes. Check the cited sources.")}</p>
      </div>
    </div>
  );
}
