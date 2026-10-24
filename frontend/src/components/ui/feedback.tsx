import { AlertTriangle, CircleAlert, Info, Loader2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted" role="status">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {label ?? "Loading…"}
    </span>
  );
}

const TONES = {
  error: { icon: CircleAlert, cls: "bg-danger-soft text-danger", role: "alert" as const },
  warning: { icon: AlertTriangle, cls: "bg-amber-50 text-warn", role: "status" as const },
  info: { icon: Info, cls: "bg-accent-soft text-accent", role: "status" as const },
};

export function Notice({ tone = "info", title, children, className }: {
  tone?: keyof typeof TONES; title?: string; children?: ReactNode; className?: string;
}) {
  const { icon: Icon, cls, role } = TONES[tone];
  return (
    <div role={role} className={cn("flex gap-2.5 rounded-lg px-3.5 py-3 text-sm", cls, className)}>
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
    <div className="rounded-lg border border-dashed border-line bg-surface px-6 py-10 text-center">
      <Icon className="mx-auto size-8 text-muted" aria-hidden />
      <h3 className="mt-3 font-display text-lg font-semibold">{title}</h3>
      {children && <p className="mx-auto mt-1 max-w-md text-sm text-muted">{children}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="mb-6">
      <h1 className="font-display text-3xl font-semibold tracking-tight">{title}</h1>
      {children && <p className="mt-2 max-w-prose text-muted">{children}</p>}
    </header>
  );
}
