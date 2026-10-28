import { tr } from "@/i18n";
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function timeAgo(iso: string, now: Date = new Date()): string {
  const seconds = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return tr("just now");
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} ${tr("min ago")}`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} ${tr("h ago")}`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} ${tr("d ago")}`;
  return new Date(iso).toLocaleDateString(typeof window !== "undefined" && window.localStorage.getItem("study-agent:locale") === "fa" ? "fa-IR" : "en-US");
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${tr(n === 1 ? one : many)}`;
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : tr("Something went wrong.");
}

export function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
