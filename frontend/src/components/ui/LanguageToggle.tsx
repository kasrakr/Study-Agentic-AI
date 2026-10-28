import { Languages } from "lucide-react";
import { useTranslation } from "@/i18n";
import { cn } from "@/lib/utils";

export default function LanguageToggle({ variant = "full" }: { variant?: "full" | "icon" | "tab" }) {
  const { locale, setLocale, t } = useTranslation();
  const label = locale === "fa" ? "Switch language to English" : "تغییر زبان به فارسی";
  const switchLanguage = () => setLocale(locale === "fa" ? "en" : "fa");

  if (variant === "tab") {
    return (
      <button type="button" onClick={switchLanguage} aria-label={label} lang={locale === "fa" ? "en" : "fa"}
        className="flex min-h-14 flex-1 flex-col items-center justify-center gap-1 rounded-xl px-1 text-[0.68rem] font-medium text-muted transition-colors active:text-ink">
        <Languages className="size-5" aria-hidden />
        <span className="max-w-full truncate">{locale === "fa" ? "EN" : "فا"}</span>
      </button>
    );
  }
  return (
    <button type="button" onClick={switchLanguage} aria-label={label} data-tip={variant === "icon" ? label : undefined}
      className={cn("tip tip-right flex w-full items-center gap-3 rounded-xl py-2 text-sm text-muted transition-colors hover:bg-hover hover:text-ink", variant === "icon" ? "justify-center" : "px-3")}>
      <Languages className="size-4 shrink-0" aria-hidden />
      {variant === "full" && <span>{t("Language")}: <bdi>{locale === "fa" ? "فارسی" : "English"}</bdi></span>}
    </button>
  );
}
