import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-accent text-white hover:bg-accent/90",
        secondary: "border border-line bg-surface text-ink hover:bg-paper",
        ghost: "text-muted hover:bg-paper hover:text-ink",
        danger: "bg-danger text-white hover:bg-danger/90",
      },
      size: { sm: "px-2.5 py-1.5 text-sm", md: "px-4 py-2 text-sm" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

interface Props extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {
  loading?: boolean;
}

export function Button({ className, variant, size, loading, disabled, children, type = "button", ...rest }: Props) {
  return (
    <button type={type} className={cn(button({ variant, size }), className)} disabled={disabled || loading} {...rest}>
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}
