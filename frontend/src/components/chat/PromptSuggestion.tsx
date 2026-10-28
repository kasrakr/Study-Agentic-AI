import { tr, useTranslation } from "@/i18n";
import type { LucideIcon } from "lucide-react";

/** A clickable starter. The parent decides whether it sends immediately or fills the composer for the student to finish. */
export default function PromptSuggestion({ icon: Icon, title, hint, onSelect }: {
  icon: LucideIcon; title: string; hint: string; onSelect: () => void;
}) {
  useTranslation();
  return (
    <button
      type="button" onClick={onSelect}
      className="glass lift group flex items-start gap-3 rounded-2xl p-4 text-left active:scale-[0.98]"
    >
      <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-tint ring-1 ring-inset ring-accent/20 transition-colors group-hover:ring-accent/50">
        <Icon className="size-[1.1rem] text-accent" aria-hidden />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium leading-snug">{title}</span>
        <span className="mt-0.5 block text-xs leading-relaxed text-muted">{hint}</span>
      </span>
    </button>
  );
}
