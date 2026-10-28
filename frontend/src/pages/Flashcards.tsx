import { tr, useTranslation } from "@/i18n";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import DocumentPicker from "@/components/documents/DocumentPicker";
import FlashcardViewer from "@/components/flashcards/FlashcardViewer";
import { Button } from "@/components/ui/Button";
import { Notice, PageHeader, Spinner } from "@/components/ui/feedback";
import { useDocuments } from "@/hooks/useDocuments";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/format";
import type { Deck } from "@/types/api";

export default function Flashcards() {
  useTranslation();
  const docs = useDocuments();
  const [params, setParams] = useSearchParams();
  const [deck, setDeck] = useState<Deck | null>(null);
  const [loading, setLoading] = useState(!!params.get("deck"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [docIds, setDocIds] = useState<string[]>([]);
  const [count, setCount] = useState(10);
  const [topic, setTopic] = useState("");
  const loadedFromUrl = useRef(false);

  // /flashcards?deck=<id> opens an existing deck (e.g. one created from chat).
  useEffect(() => {
    const id = params.get("deck");
    if (!id || loadedFromUrl.current) return;
    loadedFromUrl.current = true;
    api.getDeck(id).then(setDeck, (err) => setError(errorMessage(err))).finally(() => setLoading(false));
  }, [params]);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      setDeck(await api.generateFlashcards({ document_ids: docIds, card_count: count, topic: topic.trim() || undefined }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title={tr("Flashcards")}>{tr("Review key ideas from your documents, then mark each card so you know what to revisit.")}</PageHeader>

      {loading && <Spinner label={tr("Opening deck…")} />}
      {!loading && deck && <FlashcardViewer key={deck.id} deck={deck} onNewDeck={() => { setDeck(null); setParams({}, { replace: true }); }} />}
      {!loading && !deck && (
        docs.status === "loading" ? <Spinner label={tr("Loading documents…")} /> :
        docs.status === "error" ? <Notice tone="error">{docs.error.message}</Notice> : (
          <form className="space-y-5 glass rounded-2xl p-5" onSubmit={(e) => { e.preventDefault(); void generate(); }}>
            <DocumentPicker documents={docs.indexed} selected={docIds} onChange={setDocIds} legend={tr("Create flashcards from")} />
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="f-count" className="text-sm font-medium">{tr("Number of cards")}</label>
                <input id="f-count" type="number" min={1} max={30} value={count}
                       onChange={(e) => setCount(Math.max(1, Math.min(30, Number(e.target.value) || 1)))}
                       className="mt-1.5 block w-24 field" />
              </div>
              <div>
                <label htmlFor="f-topic" className="text-sm font-medium">Topic <span className="font-normal text-muted">{tr("(optional)")}</span></label>
                <input id="f-topic" value={topic} maxLength={200} onChange={(e) => setTopic(e.target.value)}
                       className="mt-1.5 block w-full field" />
              </div>
            </div>
            {error && <Notice tone="error" title={tr("Couldn’t create flashcards")}>{error}</Notice>}
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={docIds.length === 0} loading={busy}>{busy ? tr("Creating cards…") : tr("Create flashcards")}</Button>
              {busy && <span className="text-sm text-muted" role="status">{tr("This can take 10–30 seconds.")}</span>}
            </div>
          </form>
        )
      )}
      {!loading && deck && error && <Notice tone="error" className="mt-3">{error}</Notice>}
    </div>
  );
}
