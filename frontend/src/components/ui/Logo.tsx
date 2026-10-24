import { cn } from "@/lib/utils";

/** The Study Agent mark: a rounded tile with a four-point spark. Pure SVG/CSS, no external asset. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span className={cn("relative grid size-9 shrink-0 place-items-center rounded-xl bg-brand-gradient shadow-glow ring-1 ring-inset ring-white/20", className)} aria-hidden>
      <svg viewBox="0 0 24 24" className="size-[55%] text-white" fill="currentColor">
        <path d="M12 2.5c.5 4.6 2.9 7 7.5 7.5-4.6.5-7 2.9-7.5 7.5-.5-4.6-2.9-7-7.5-7.5 4.6-.5 7-2.9 7.5-7.5Z" />
        <path d="M19 15.5c.2 1.8 1.2 2.8 3 3-1.8.2-2.8 1.2-3 3-.2-1.8-1.2-2.8-3-3 1.8-.2 2.8-1.2 3-3Z" opacity=".75" />
      </svg>
    </span>
  );
}
