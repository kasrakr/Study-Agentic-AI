import { BookOpenText, BrainCircuit, Layers, LayoutDashboard, Library, ListChecks, MessageSquareText, type LucideIcon } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/chat", label: "Study chat", icon: MessageSquareText },
  { to: "/library", label: "My documents", icon: Library },
  { to: "/quiz", label: "Quiz studio", icon: ListChecks },
  { to: "/flashcards", label: "Flashcards", icon: Layers },
];

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <span className="brand-mark size-10 shrink-0 rounded-[13px] text-white">
        <BookOpenText className="size-5" aria-hidden />
      </span>
      <span className="min-w-0">
        <span className="brand-copy block text-[15px] font-semibold text-slate-50">Study Agent</span>
        <span className="mt-0.5 block text-[10px] font-medium tracking-[0.13em] text-slate-500">AI LEARNING SPACE</span>
      </span>
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
              "app-nav-link flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium",
              isActive && "active",
            )
          }
        >
          <Icon className="size-[17px] shrink-0" strokeWidth={1.8} aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

export default function AppShell() {
  return (
    <div className="app-shell flex min-h-full flex-col md:flex-row">
      <header className="mobile-header md:hidden">
        <Brand />
        <Nav className="mt-3 overflow-x-auto pb-1" />
      </header>

      <aside className="app-sidebar hidden w-60 shrink-0 flex-col gap-8 px-4 py-6 md:flex">
        <Brand />
        <div className="flex flex-col gap-3">
          <p className="sidebar-eyebrow">WORKSPACE</p>
          <Nav className="flex-col" />
        </div>
        <div className="mt-auto rounded-2xl border border-white/[0.07] bg-white/[0.025] p-3.5">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
            <BrainCircuit className="size-4 text-sky-300" aria-hidden />
            Built for deep learning
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
            Your files stay on this machine; questions and document text are sent to OpenAI.
          </p>
          <div className="mt-3 flex items-center gap-2 border-t border-white/[0.07] pt-3 text-[10px] text-slate-600">
            <span className="size-1.5 rounded-full bg-sky-400" aria-hidden />
            Personal study workspace
          </div>
        </div>
      </aside>

      <main className="app-main min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
        <div className="page-container mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
