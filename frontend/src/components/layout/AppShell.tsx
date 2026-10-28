import { ChevronsLeft, ChevronsRight, Layers, LayoutDashboard, Library, ListChecks, MessageSquareText, type LucideIcon } from "lucide-react";
import { useCallback, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { LogoMark } from "@/components/ui/Logo";
import ThemeToggle from "@/components/ui/ThemeToggle";
import LanguageToggle from "@/components/ui/LanguageToggle";
import { useTranslation } from "@/i18n";
import { ToastProvider } from "@/components/ui/Toast";
import { useTheme, type Theme } from "@/hooks/useTheme";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

// Only routes that exist in App.tsx belong here.
const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/chat", label: "Study chat", icon: MessageSquareText },
  { to: "/library", label: "Library", icon: Library },
  { to: "/quiz", label: "Quiz", icon: ListChecks },
  { to: "/flashcards", label: "Flashcards", icon: Layers },
];

const COLLAPSE_KEY = "study-agent:sidebar-collapsed";

function useStoredFlag(key: string, initial: boolean) {
  const [value, setValue] = useState(() => {
    try { return window.localStorage.getItem(key) === "1" ? true : window.localStorage.getItem(key) === "0" ? false : initial; }
    catch { return initial; }
  });
  const set = useCallback((next: boolean) => {
    setValue(next);
    try { window.localStorage.setItem(key, next ? "1" : "0"); } catch { /* storage unavailable: keep the in-memory value */ }
  }, [key]);
  return [value, set] as const;
}

function Brand({ collapsed }: { collapsed: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="flex min-w-0 items-center gap-3">
      <LogoMark />
      <span className={cn("truncate text-[1.05rem] font-semibold tracking-tight transition-opacity duration-200", collapsed && "sr-only")}>{t("Study Agent")}</span>
    </div>
  );
}

function Sidebar({ collapsed, onToggle, theme, onToggleTheme }: { collapsed: boolean; onToggle: () => void; theme: Theme; onToggleTheme: () => void }) {
  const { t } = useTranslation();
  return (
    <aside
      className={cn(
        "relative z-30 hidden shrink-0 flex-col border-e border-line bg-paper-2/70 py-5 transition-[width,padding] duration-200 ease-out md:flex",
        collapsed ? "w-[4.75rem] px-3" : "w-64 px-4",
      )}
    >
      <div className={cn("flex items-center", collapsed ? "justify-center" : "justify-between")}>
        {collapsed ? <LogoMark /> : <Brand collapsed={false} />}
      </div>

      <nav aria-label={t("Main navigation")} className="mt-8 flex flex-col gap-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end
            data-tip={collapsed ? t(label) : undefined}
            className={({ isActive }) =>
              cn(
                "tip tip-side group relative flex items-center gap-3 rounded-xl py-2.5 text-sm font-medium transition-colors duration-150",
                collapsed ? "justify-center px-0" : "px-3",
                isActive ? "bg-accent-soft text-ink" : "text-muted hover:bg-hover hover:text-ink",
              )
            }
          >
            {({ isActive }) => (
              <>
                <span aria-hidden className={cn("absolute start-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-e-full bg-gradient-to-b from-cyan to-accent transition-opacity", isActive ? "opacity-100" : "opacity-0")} />
                <Icon className={cn("size-[1.15rem] shrink-0 transition-colors", isActive ? "text-accent" : "group-hover:text-ink")} aria-hidden />
                <span className={cn(collapsed && "sr-only")}>{t(label)}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto space-y-3">
        {!collapsed && (
          <p className="px-1 text-xs leading-relaxed text-faint">
            {t("Your files stay on this machine; questions and document text are sent to OpenAI.")}
            <br />
            <span className="text-gradient">{t("Made by Kasra Karimian")}</span>
          </p>
        )}
        <LanguageToggle variant={collapsed ? "icon" : "full"} />
        <ThemeToggle theme={theme} onToggle={onToggleTheme} variant={collapsed ? "icon" : "full"} />
        <button
          type="button" onClick={onToggle} aria-pressed={collapsed} aria-label={t(collapsed ? "Expand sidebar" : "Collapse sidebar")}
          data-tip={t(collapsed ? "Expand sidebar" : "Collapse sidebar")}
          className={cn("tip tip-side flex items-center gap-3 rounded-xl py-2 text-sm text-muted transition-colors hover:bg-hover hover:text-ink", collapsed ? "w-full justify-center" : "w-full px-3")}
        >
          {collapsed ? <ChevronsRight className="size-4" aria-hidden /> : <ChevronsLeft className="size-4" aria-hidden />}
          {!collapsed && <span>{t("Collapse")}</span>}
        </button>
      </div>
    </aside>
  );
}

function MobileNav({ theme, onToggleTheme }: { theme: Theme; onToggleTheme: () => void }) {
  const { t } = useTranslation();
  return (
    <nav aria-label={t("Mobile navigation")} className="glass-strong z-30 flex shrink-0 rounded-none border-x-0 border-b-0 px-1 pb-[env(safe-area-inset-bottom)] md:hidden">
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to} to={to} end
          className={({ isActive }) =>
            cn(
              "flex min-h-14 flex-1 flex-col items-center justify-center gap-1 rounded-xl px-1 text-[0.68rem] font-medium transition-colors",
              isActive ? "text-accent" : "text-muted active:text-ink",
            )
          }
        >
          <Icon className="size-5" aria-hidden />
          <span className="max-w-full truncate">{t(label)}</span>
        </NavLink>
      ))}
      <LanguageToggle variant="tab" />
      <ThemeToggle theme={theme} onToggle={onToggleTheme} variant="tab" />
    </nav>
  );
}

export default function AppShell() {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useStoredFlag(COLLAPSE_KEY, false);
  const { theme, toggle: toggleTheme } = useTheme();
  const { pathname } = useLocation();
  const fullBleed = pathname === "/chat"; // the chat manages its own scrolling so the composer stays anchored

  return (
    <ToastProvider>
      <div className="ambient relative flex h-dvh flex-col overflow-hidden md:flex-row">
        <a href="#main" className="sr-only z-[70] rounded-lg bg-brand px-3 py-2 text-sm font-medium text-white focus:not-sr-only focus:fixed focus:start-3 focus:top-3">
          {t("Skip to main content")}
        </a>
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} theme={theme} onToggleTheme={toggleTheme} />

        <main id="main" tabIndex={-1} className={cn("relative min-h-0 min-w-0 flex-1 outline-none", fullBleed ? "flex flex-col overflow-hidden" : "overflow-y-auto")}>
          {fullBleed ? (
            <Outlet />
          ) : (
            <div key={pathname} className="mx-auto max-w-5xl px-4 py-6 animate-fade-up md:px-8 md:py-10">
              <Outlet />
            </div>
          )}
        </main>

        <MobileNav theme={theme} onToggleTheme={toggleTheme} />
      </div>
    </ToastProvider>
  );
}
