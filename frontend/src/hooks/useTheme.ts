import { useCallback, useEffect, useState } from "react";

export type Theme = "dark" | "light";

export const THEME_KEY = "study-agent:theme";
const META_COLORS: Record<Theme, string> = { dark: "#070b16", light: "#f4f7fb" };

/** Saved choice first, then the OS preference, then dark (the original look). */
function readInitialTheme(): Theme {
  try {
    const saved = window.localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch { /* storage unavailable: fall through to the OS preference */ }
  try {
    if (window.matchMedia?.("(prefers-color-scheme: light)").matches) return "light";
  } catch { /* matchMedia unavailable (e.g. tests) */ }
  return "dark";
}

function applyTheme(theme: Theme, animate: boolean) {
  const root = document.documentElement;
  if (animate) {
    root.classList.add("theme-transition");
    window.setTimeout(() => root.classList.remove("theme-transition"), 300);
  }
  root.dataset.theme = theme;
  document.querySelector('meta[name="color-scheme"]')?.setAttribute("content", theme);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", META_COLORS[theme]);
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(readInitialTheme);

  // Keep the DOM in sync on first render (the inline script in index.html normally did this already).
  useEffect(() => { applyTheme(theme, false); }, [theme]);

  const setTheme = useCallback((next: Theme) => {
    applyTheme(next, true);
    setThemeState(next);
    try { window.localStorage.setItem(THEME_KEY, next); } catch { /* keep the in-memory value */ }
  }, []);

  const toggle = useCallback(() => setTheme(theme === "dark" ? "light" : "dark"), [theme, setTheme]);

  // Follow the OS setting live, but only while the user hasn't picked a theme themselves.
  useEffect(() => {
    let mq: MediaQueryList | undefined;
    try { mq = window.matchMedia?.("(prefers-color-scheme: light)"); } catch { return; }
    if (!mq) return;
    const onChange = (e: MediaQueryListEvent) => {
      try { if (window.localStorage.getItem(THEME_KEY)) return; } catch { /* ignore */ }
      const next: Theme = e.matches ? "light" : "dark";
      applyTheme(next, true);
      setThemeState(next);
    };
    mq.addEventListener?.("change", onChange);
    return () => mq?.removeEventListener?.("change", onChange);
  }, []);

  return { theme, setTheme, toggle };
}
