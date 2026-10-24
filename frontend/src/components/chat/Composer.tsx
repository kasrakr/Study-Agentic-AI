import { SendHorizontal, Square, CornerDownLeft } from "lucide-react";
import { useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/Button";

export default function Composer({ busy, onSend, onStop, placeholder }: {
  busy: boolean; onSend: (text: string) => void; onStop: () => void; placeholder?: string;
}) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  function submit() {
    const value = text.trim();
    if (!value || busy) return;
    onSend(value);
    setText("");
    if (ref.current) ref.current.style.height = "auto";
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="composer-form flex items-end">
      <label htmlFor="composer" className="sr-only">Ask a question about your study materials</label>
      <textarea
        id="composer" ref={ref} rows={1} value={text} maxLength={4000} placeholder={placeholder ?? "Ask about your study materials…"}
        onChange={(e) => {
          setText(e.target.value);
          e.target.style.height = "auto";
          e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
        }}
        onKeyDown={onKeyDown}
        className="max-h-40 min-h-10 min-w-0 flex-1 resize-none rounded-lg px-2 py-2 outline-none"
      />
      {busy ? (
        <Button variant="secondary" onClick={onStop} className="composer-send shrink-0" aria-label="Stop generating"><Square className="size-4" aria-hidden /> <span className="hidden sm:inline">Stop</span></Button>
      ) : (
        <Button type="submit" disabled={!text.trim()} className="composer-send shrink-0" aria-label="Send message"><SendHorizontal className="size-4" aria-hidden /> <span className="hidden sm:inline">Send</span></Button>
      )}
    </form>
  );
}
