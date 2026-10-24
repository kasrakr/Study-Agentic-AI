import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex select-none items-center justify-center gap-2 rounded-xl font-medium transition-all duration-150 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100",
  {
    variants: {
      variant: {
        primary: "bg-brand-gradient text-white shadow-glow hover:brightness-110",
        secondary: "glass text-ink hover:border-line-strong hover:bg-surface-strong",
        ghost: "text-muted hover:bg-hover hover:text-ink",
        danger: "bg-danger/90 text-[#1a0a0a] hover:bg-danger",
      },
      size: { sm: "px-3 py-1.5 text-sm", md: "px-4 py-2 text-sm" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

interface Props extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {
  loading?: boolean;
}

export function Button({ className, variant, size, loading, disabled, children, type = "button", ...rest }: Props) {
  return (
    <button type={type} className={cn(button({ variant, size }), className)} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

/** Class string for links that should look like a Button (keeps the link a real <a>/<Link>). */
export const buttonClass = (variant: VariantProps<typeof button>["variant"] = "primary", size: VariantProps<typeof button>["size"] = "md") =>
  button({ variant, size });
