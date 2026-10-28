import { tr, useTranslation } from "@/i18n";
import { ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CardDifficulty, Deck, Flashcard } from "@/types/api";

const RATINGS: { value: CardDifficulty; label: string; cls: string }[] = [
  { value: "easy", label: "Easy", cls: "border-ok/40 bg-ok-soft text-ok hover:bg-ok/20" },
  { value: "medium", label: "Medium", cls: "border-warn/40 bg-warn-soft text-warn hover:bg-warn/20" },
  { value: "difficult", label: "Difficult", cls: "border-danger/40 bg-danger-soft text-danger hover:bg-danger/20" },
];

export default function FlashcardViewer({ deck: initial, onNewDeck }: { deck: Deck; onNewDeck: () => void }) {
  useTranslation();
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
      <section className="glass rounded-2xl p-6 text-center" aria-labelledby="done-heading">
        <h2 id="done-heading" className="text-2xl font-semibold">{tr("Deck complete")}</h2>
        <p className="mt-2 text-sm text-muted">
          {count("easy")} {tr("easy")} · {count("medium")} {tr("medium")} · {count("difficult")} {tr("difficult")} · {count(null)} {tr("not rated")}
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <Button onClick={() => { setOrder(cards.map((c) => c.id)); setIndex(0); setRevealed(false); }}><RotateCcw className="size-4" aria-hidden /> {tr("Study again")}</Button>
          {hard.length > 0 && <Button variant="secondary" onClick={() => { setOrder(hard); setIndex(0); setRevealed(false); }}>Only difficult ({hard.length})</Button>}
          <Button variant="ghost" onClick={onNewDeck}>{tr("New deck")}</Button>
        </div>
      </section>
    );
  }

  return (
    <section aria-label={tr("Flashcards")}>
      <div className="mb-2 flex items-center justify-between text-sm text-muted">
        <span aria-live="polite">Card {index + 1} of {order.length} · {initial.title}</span>
        <button type="button" onClick={onNewDeck} className="underline">{tr("New deck")}</button>
      </div>

      <div className="glass-strong rounded-2xl p-6 sm:p-8" aria-live="polite">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-accent">{tr(revealed ? "Answer" : "Question")} · {card!.topic}</p>
        <p key={revealed ? "back" : "front"} className="mt-3 min-h-24 whitespace-pre-wrap text-xl leading-relaxed animate-fade-in">{revealed ? card!.back : card!.front}</p>
        {revealed && <p className="mt-4 border-t border-line pt-3 text-sm text-muted"><span className="font-medium text-ink">Q:</span> {card!.front}</p>}
        <p className="mt-4 text-xs text-muted">
          Source:{" "}
          <a href={api.documentFileUrl(card!.document_id, card!.page_number)} target="_blank" rel="noopener noreferrer" className="underline">
            {card!.filename}{card!.page_number != null && `, ${tr("page")} ${card!.page_number}`}
          </a>
        </p>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <Button variant="secondary" onClick={() => go(-1)} disabled={index === 0}><ChevronLeft className="size-4" aria-hidden /> {tr("Previous")}</Button>
        <Button onClick={() => setRevealed((r) => !r)} aria-pressed={revealed}>{revealed ? tr("Show question") : tr("Reveal answer")}</Button>
        <Button variant="secondary" onClick={() => go(1)}>{index === order.length - 1 ? tr("Finish") : tr("Next")} <ChevronRight className="size-4" aria-hidden /></Button>
      </div>

      {revealed && (
        <div className="mt-5" role="group" aria-label={tr("How hard was this card?")}>
          <p className="mb-2 text-sm font-medium">{tr("How hard was this card?")}</p>
          <div className="flex flex-wrap gap-2">
            {RATINGS.map((r) => (
              <button key={r.value} type="button" disabled={saving} aria-pressed={card!.difficulty === r.value} onClick={() => void rate(r.value)}
                      className={cn("rounded-xl border px-4 py-2 text-sm font-medium transition-all active:scale-[0.97] disabled:opacity-60", r.cls, card!.difficulty === r.value && "ring-2 ring-current")}>
                {tr(r.label)}
              </button>
            ))}
          </div>
        </div>
      )}
      {error && <Notice tone="error" className="mt-3" title={tr("Couldn’t save your rating")}>{error}</Notice>}
      <p className="mt-4 text-xs text-muted">{tr("Keyboard: ← → to move between cards.")}</p>
    </section>
  );
}
