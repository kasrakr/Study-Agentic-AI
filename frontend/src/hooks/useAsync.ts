import { useCallback, useEffect, useRef, useState } from "react";

export type AsyncState<T> =
  | { status: "loading"; data: null; error: null }
  | { status: "success"; data: T; error: null }
  | { status: "error"; data: null; error: Error };

/** Runs `fn` on mount and on `reload()`, ignoring results from stale or aborted runs. */
export function useAsync<T>(fn: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading", data: null, error: null });
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const controller = useRef<AbortController | null>(null);

  const run = useCallback(() => {
    controller.current?.abort();
    const ctrl = new AbortController();
    controller.current = ctrl;
    setState({ status: "loading", data: null, error: null });
    fnRef.current(ctrl.signal).then(
      (data) => !ctrl.signal.aborted && setState({ status: "success", data, error: null }),
      (error: unknown) => {
        if (ctrl.signal.aborted) return;
        setState({ status: "error", data: null, error: error instanceof Error ? error : new Error(String(error)) });
      },
    );
  }, []);

  useEffect(() => {
    run();
    return () => controller.current?.abort();
  }, [run]);

  return { ...state, reload: run };
}
