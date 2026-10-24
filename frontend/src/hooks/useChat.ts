import { useCallback, useEffect, useRef, useState } from "react";
import { api, streamChat } from "@/lib/api";
import { applyStreamEvent, fromStored, pendingAssistant, userMessage, type ChatMessage } from "@/lib/chatState";
import { errorMessage } from "@/lib/format";

function newConversationId(): string {
  return crypto.randomUUID().replaceAll("-", "");
}

export function useChat(onTurnFinished?: () => void) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const conversationRef = useRef<string | null>(null);
  const counter = useRef(0);
  const finishedRef = useRef(onTurnFinished);
  finishedRef.current = onTurnFinished;

  const nextId = () => `m${++counter.current}`;
  const updateLast = (fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((list) => list.map((m, i) => (i === list.length - 1 ? fn(m) : m)));

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const send = useCallback(async (question: string, documentIds: string[]) => {
    if (abortRef.current) return; // one turn at a time
    const cid = conversationRef.current ?? newConversationId();
    conversationRef.current = cid;
    setConversationId(cid);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setBusy(true);
    setMessages((list) => [...list, userMessage(nextId(), question), pendingAssistant(nextId())]);
    try {
      for await (const ev of streamChat(
        { question, conversation_id: cid, document_ids: documentIds.length ? documentIds : undefined }, ctrl.signal)) {
        updateLast((m) => applyStreamEvent(m, ev));
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        updateLast((m) => ({ ...m, status: "stopped", steps: m.steps.map((s) => ({ ...s, phase: "done" as const })) }));
      } else {
        updateLast((m) => ({ ...m, status: "error", error: errorMessage(err) }));
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
      finishedRef.current?.();
    }
  }, []);

  const open = useCallback(async (id: string) => {
    abortRef.current?.abort();
    setLoadError(null);
    try {
      const detail = await api.getConversation(id);
      conversationRef.current = id;
      setConversationId(id);
      setMessages(detail.messages.map((m) => fromStored(m, nextId())));
    } catch (err) {
      setLoadError(errorMessage(err));
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    conversationRef.current = null;
    setConversationId(null);
    setMessages([]);
    setLoadError(null);
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  return { messages, conversationId, busy, loadError, send, stop, open, reset };
}
