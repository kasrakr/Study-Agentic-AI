import { useMemo } from "react";
import { useAsync } from "@/hooks/useAsync";
import { api } from "@/lib/api";

/** Document list plus the subset that is indexed (the only ones usable for chat, quizzes and flashcards). */
export function useDocuments() {
  const state = useAsync((signal) => api.listDocuments(signal));
  const indexed = useMemo(() => state.data?.documents.filter((d) => d.status === "indexed") ?? [], [state.data]);
  return { ...state, indexed };
}
