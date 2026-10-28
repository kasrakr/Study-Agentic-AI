import { tr, useTranslation } from "@/i18n";
import { Check, Copy } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";

/** Copies text to the clipboard. Shows a check mark briefly and reports failures through a toast. */
export default function CopyButton({ text, label = tr("Copy"), className, withLabel = false }: {
  text: string | (() => string); label?: string; className?: string; withLabel?: boolean;
}) {
  useTranslation();
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const toast = useToast();
  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(typeof text === "function" ? text() : text);
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 1600);
    } catch {
      toast.push("Couldn’t copy to the clipboard. Select the text and copy it manually.", "error");
    }
  }

  return (
    <button
      type="button" onClick={() => void copy()} aria-label={copied ? tr("Copied") : label} data-tip={copied ? tr("Copied") : label}
      className={cn("tip inline-flex items-center gap-1.5 rounded-lg p-1.5 text-xs text-muted transition-colors hover:bg-hover hover:text-ink", className)}
    >
      {copied ? <Check className="size-3.5 text-ok" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
      {withLabel && <span>{copied ? tr("Copied") : label}</span>}
    </button>
  );
}
