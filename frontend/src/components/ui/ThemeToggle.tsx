import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Theme } from "@/hooks/useTheme";

interface Props {
  theme: Theme;
  onToggle: () => void;
  /** "full" shows the label (sidebar), "icon" is icon-only (collapsed sidebar), "tab" matches the mobile bottom nav. */
  variant?: "full" | "icon" | "tab";
  className?: string;
}

export default function ThemeToggle({ theme, onToggle, variant = "full", className }: Props) {
  const isLight = theme === "light";
  const label = isLight ? "Switch to dark mode" : "Switch to light mode";
  const Icon = isLight ? Moon : Sun;

  if (variant === "tab") {
    return (
      <button
        type="button" onClick={onToggle} aria-label={label}
        className={cn("flex min-h-14 flex-1 flex-col items-center justify-center gap-1 rounded-xl px-1 text-[0.68rem] font-medium text-muted transition-colors active:text-ink", className)}
      >
        <Icon className="size-5" aria-hidden />
        <span className="max-w-full truncate">{isLight ? "Dark" : "Light"}</span>
      </button>
    );
  }

  return (
    <button
      type="button" onClick={onToggle} aria-label={label} data-tip={variant === "icon" ? label : undefined}
      className={cn(
        "tip tip-right flex w-full items-center gap-3 rounded-xl py-2 text-sm text-muted transition-colors hover:bg-hover hover:text-ink",
        variant === "icon" ? "justify-center" : "px-3",
        className,
      )}
    >
      <Icon className="size-4" aria-hidden />
      {variant === "full" && <span>{isLight ? "Dark mode" : "Light mode"}</span>}
    </button>
  );
}
