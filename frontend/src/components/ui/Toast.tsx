import { CheckCircle2, CircleAlert, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type ToastTone = "success" | "error" | "info";
interface ToastItem { id: number; tone: ToastTone; message: string }
interface ToastApi { push: (message: string, tone?: ToastTone) => void }

const ToastContext = createContext<ToastApi | null>(null);
const NOOP: ToastApi = { push: () => {} };

/** Components can call this anywhere; outside a <ToastProvider> (e.g. in isolated tests) it does nothing. */
export function useToast(): ToastApi {
  return useContext(ToastContext) ?? NOOP;
}

const ICONS = { success: CheckCircle2, error: CircleAlert, info: Info };
const COLORS: Record<ToastTone, string> = { success: "text-ok", error: "text-danger", info: "text-accent" };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: number) => setItems((list) => list.filter((t) => t.id !== id)), []);
  const push = useCallback((message: string, tone: ToastTone = "info") => {
    const id = ++counter.current;
    setItems((list) => [...list.slice(-3), { id, tone, message }]);
    window.setTimeout(() => dismiss(id), tone === "error" ? 6000 : 3500);
  }, [dismiss]);
  const api = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 md:bottom-6 md:items-end md:px-6" role="status" aria-live="polite">
        {items.map((t) => {
          const Icon = ICONS[t.tone];
          return (
            <div key={t.id} className="glass-strong pointer-events-auto flex max-w-sm items-start gap-2.5 rounded-xl px-3.5 py-2.5 text-sm animate-toast">
              <Icon className={cn("mt-0.5 size-4 shrink-0", COLORS[t.tone])} aria-hidden />
              <p className="min-w-0 flex-1 break-words">{t.message}</p>
              <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss notification" className="-mr-1 rounded-md p-1 text-muted transition-colors hover:bg-hover hover:text-ink">
                <X className="size-3.5" aria-hidden />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
