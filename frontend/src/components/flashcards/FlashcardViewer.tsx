import { ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CardDifficulty, Deck, Flashcard } from "@/types/api";

const RATINGS: { value: CardDifficulty; label: string; cls: string }[] = [
  { value: "easy", label: "Easy", cls: "border-emerald-300 bg-emerald-50 text-ok" },
  { value: "medium", label: "Medium", cls: "border-amber-300 bg-amber-50 text-warn" },
  { value: "difficult", label: "Difficult", cls: "border-red-300 bg-danger-soft text-danger" },
];

export default function FlashcardViewer({ deck: initial, onNewDeck }: { deck: Deck; onNewDeck: () => void }) {
  const [cards, setCards] = useState<Flashcard[]>(initial.cards);
  const [order, setOrder] = useState<string[]>(initial.cards.map((c) => c.id)); // which cards, in what order
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const byId = new Map(cards.map((c) => [c.id, c]));
  const finished = index >= order.length;
  const card = finished ? null : byId.get(order[index])!;

  const go = useCallback((delta: number) => {
    setIndex((i) => Math.max(0, Math.min(order.length, i + delta)));
    setRevealed(false);
    setError(null);
  }, [order.length]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (e.key === "ArrowRight") go(1);
      if (e.key === "ArrowLeft") go(-1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  async function rate(difficulty: CardDifficulty) {
    if (!card) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.rateCard(card.id, difficulty);
      setCards((list) => list.map((c) => (c.id === updated.id ? updated : c)));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (finished) {
    const count = (d: CardDifficulty | null) => cards.filter((c) => c.difficulty === d).length;
    const hard = cards.filter((c) => c.difficulty === "difficult").map((c) => c.id);
    return (
      <section className="rounded-lg border border-line bg-surface p-6 text-center" aria-labelledby="done-heading">
        <h2 id="done-heading" className="font-display text-2xl font-semibold">Deck complete</h2>
        <p className="mt-2 text-sm text-muted">
          {count("easy")} easy · {count("medium")} medium · {count("difficult")} difficult · {count(null)} not rated
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <Button onClick={() => { setOrder(cards.map((c) => c.id)); setIndex(0); setRevealed(false); }}><RotateCcw className="size-4" aria-hidden /> Study again</Button>
          {hard.length > 0 && <Button variant="secondary" onClick={() => { setOrder(hard); setIndex(0); setRevealed(false); }}>Only difficult ({hard.length})</Button>}
          <Button variant="ghost" onClick={onNewDeck}>New deck</Button>
        </div>
      </section>
    );
  }

  return (
    <section aria-label="Flashcards">
      <div className="mb-2 flex items-center justify-between text-sm text-muted">
        <span aria-live="polite">Card {index + 1} of {order.length} · {initial.title}</span>
        <button type="button" onClick={onNewDeck} className="underline">New deck</button>
      </div>

      <div className="rounded-xl border border-line bg-surface p-6 sm:p-8" aria-live="polite">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">{revealed ? "Answer" : "Question"} · {card!.topic}</p>
        <p className="mt-3 min-h-24 whitespace-pre-wrap font-display text-xl leading-relaxed">{revealed ? card!.back : card!.front}</p>
        {revealed && <p className="mt-4 border-t border-line pt-3 text-sm text-muted"><span className="font-medium text-ink">Q:</span> {card!.front}</p>}
        <p className="mt-4 text-xs text-muted">
          Source:{" "}
          <a href={api.documentFileUrl(card!.document_id, card!.page_number)} target="_blank" rel="noopener noreferrer" className="underline">
            {card!.filename}{card!.page_number != null && `, page ${card!.page_number}`}
          </a>
        </p>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <Button variant="secondary" onClick={() => go(-1)} disabled={index === 0}><ChevronLeft className="size-4" aria-hidden /> Previous</Button>
        <Button onClick={() => setRevealed((r) => !r)} aria-pressed={revealed}>{revealed ? "Show question" : "Reveal answer"}</Button>
        <Button variant="secondary" onClick={() => go(1)}>{index === order.length - 1 ? "Finish" : "Next"} <ChevronRight className="size-4" aria-hidden /></Button>
      </div>

      {revealed && (
        <div className="mt-5" role="group" aria-label="How hard was this card?">
          <p className="mb-2 text-sm font-medium">How hard was this card?</p>
          <div className="flex flex-wrap gap-2">
            {RATINGS.map((r) => (
              <button key={r.value} type="button" disabled={saving} aria-pressed={card!.difficulty === r.value} onClick={() => void rate(r.value)}
                      className={cn("rounded-md border px-4 py-2 text-sm font-medium disabled:opacity-60", r.cls, card!.difficulty === r.value && "ring-2 ring-current")}>
                {r.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {error && <Notice tone="error" className="mt-3" title="Couldn’t save your rating">{error}</Notice>}
      <p className="mt-4 text-xs text-muted">Keyboard: ← → to move between cards.</p>
    </section>
  );
}
