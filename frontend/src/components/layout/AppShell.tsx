import { BookOpenText, LayoutDashboard, type LucideIcon } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

// Only pages that exist are listed. Later phases add Library, Study chat, Quiz, Flashcards.
const NAV_ITEMS: NavItem[] = [{ to: "/", label: "Dashboard", icon: LayoutDashboard }];

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid size-8 place-items-center rounded-md bg-accent text-white">
        <BookOpenText className="size-4.5" aria-hidden />
      </span>
      <span className="font-display text-lg font-semibold tracking-tight">Study AI Agent</span>
    </div>
  );
}

function Nav({ className }: { className?: string }) {
  return (
    <nav aria-label="Main" className={cn("flex gap-1", className)}>
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              isActive ? "bg-accent-soft text-accent" : "text-muted hover:bg-paper hover:text-ink",
            )
          }
        >
          <Icon className="size-4" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

export default function AppShell() {
  return (
    <div className="flex min-h-full flex-col md:flex-row">
      <header className="border-b border-line bg-surface px-4 py-3 md:hidden">
        <Brand />
        <Nav className="mt-3 overflow-x-auto" />
      </header>

      <aside className="hidden w-60 shrink-0 flex-col gap-8 border-r border-line bg-surface px-4 py-6 md:flex">
        <Brand />
        <Nav className="flex-col" />
        <p className="mt-auto px-3 text-xs leading-relaxed text-muted">
          Single-user local app. Your files stay on this machine; questions and document text are sent to OpenAI.
        </p>
      </aside>

      <main className="min-w-0 flex-1 px-5 py-8 md:px-10 md:py-10">
        <div className="mx-auto max-w-3xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
