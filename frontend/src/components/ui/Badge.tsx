import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const TONES = {
  neutral: "bg-paper text-muted",
  accent: "bg-accent-soft text-accent",
  ok: "bg-emerald-50 text-ok",
  warn: "bg-amber-50 text-warn",
  danger: "bg-danger-soft text-danger",
  web: "bg-violet-50 text-violet-800",
};

export function Badge({ tone = "neutral", children, className }: { tone?: keyof typeof TONES; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", TONES[tone], className)}>
      {children}
    </span>
  );
}
