import { AlertTriangle, CircleAlert, Info, Loader2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted" role="status">
      <Loader2 className="size-4 animate-spin text-accent" aria-hidden />
      {label ?? "Loading…"}
    </span>
  );
}

/** Shimmer-free skeleton block (no continuous animation beyond a slow fade). */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-xl bg-hover", className)} />;
}

const TONES = {
  error: { icon: CircleAlert, cls: "border-danger/30 bg-danger-soft text-danger", role: "alert" as const },
  warning: { icon: AlertTriangle, cls: "border-warn/30 bg-warn-soft text-warn", role: "status" as const },
  info: { icon: Info, cls: "border-accent/25 bg-accent-soft text-accent", role: "status" as const },
};

export function Notice({ tone = "info", title, children, className }: {
  tone?: keyof typeof TONES; title?: string; children?: ReactNode; className?: string;
}) {
  const { icon: Icon, cls, role } = TONES[tone];
  return (
    <div role={role} className={cn("flex gap-2.5 rounded-xl border px-3.5 py-3 text-sm animate-fade-in", cls, className)}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn(title && "mt-0.5", "text-ink/80")}>{children}</div>}
      </div>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action }: {
  icon: LucideIcon; title: string; children?: ReactNode; action?: ReactNode;
}) {
  return (
    <div className="glass rounded-2xl border-dashed px-6 py-12 text-center">
      <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-tint ring-1 ring-inset ring-accent/20">
        <Icon className="size-6 text-accent" aria-hidden />
      </span>
      <h3 className="mt-4 text-lg font-semibold">{title}</h3>
      {children && <p className="mx-auto mt-1.5 max-w-md text-sm leading-relaxed text-muted">{children}</p>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="mb-8">
      <h1 className="text-gradient text-3xl font-semibold tracking-tight sm:text-[2.1rem]">{title}</h1>
      {children && <p className="mt-2 max-w-prose leading-relaxed text-muted">{children}</p>}
    </header>
  );
}

/** Small uppercase label used above groups of content. */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn("text-xs font-semibold uppercase tracking-[0.08em] text-faint", className)}>{children}</p>;
}
