import { FileUp, GraduationCap, Layers, Lightbulb, ListChecks, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { buttonClass } from "@/components/ui/Button";
import PromptSuggestion from "./PromptSuggestion";

export interface Starter {
  icon: LucideIcon;
  title: string;
  hint: string;
  /** "send" asks the agent straight away; "fill" puts text in the composer so the student can finish it. */
  mode: "send" | "fill";
  prompt: string;
}

export const STARTERS: Starter[] = [
  { icon: Lightbulb, title: "Explain a difficult concept", hint: "From my notes, in simple terms", mode: "send", prompt: "Explain the hardest concept in my notes in simple terms" },
  { icon: ListChecks, title: "Create a quiz", hint: "From my uploaded documents", mode: "send", prompt: "Quiz me on my documents" },
  { icon: GraduationCap, title: "Help me solve an exam question", hint: "Paste the question and I’ll work through it", mode: "fill", prompt: "Help me solve this exam question: " },
  { icon: Layers, title: "Generate flashcards", hint: "For my next exam", mode: "send", prompt: "Create flashcards from my documents" },
];

/** CSS-only orb: concentric rings and a soft radial glow. No images, no animation. */
function Orb() {
  return (
    <div className="relative mx-auto grid size-24 place-items-center" aria-hidden>
      <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle,rgb(59_130_246/0.45),transparent_68%)] blur-xl" />
      <div className="absolute inset-1 rounded-full border border-accent/20" />
      <div className="absolute inset-4 rounded-full border border-cyan/25" />
      <div className="relative size-10 rounded-full bg-[radial-gradient(circle_at_30%_30%,#bae6fd,#3b82f6_55%,#1d4ed8)] shadow-glow ring-1 ring-white/30" />
    </div>
  );
}

export default function ChatEmptyState({ indexedCount, loading, onPick }: {
  indexedCount: number; loading: boolean; onPick: (starter: Starter) => void;
}) {
  return (
    <div className="mx-auto flex min-h-full max-w-2xl flex-col justify-center px-1 py-8 text-center animate-fade-up">
      <Orb />
    <h2 className="text-gradient mt-6 mb-2 text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
      What are you studying today?
    </h2>
      <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-muted sm:text-base">
        Ask questions about your notes, get step-by-step explanations with cited pages, and turn your material into quizzes and flashcards.
      </p>

      {loading ? null : indexedCount === 0 ? (
        <div className="glass mx-auto mt-8 max-w-md rounded-2xl p-5">
          <p className="text-sm leading-relaxed text-muted">You haven’t indexed any documents yet. Upload some in the Library for page-level citations.</p>
          <Link to="/library" className={`${buttonClass("primary")} mt-4`}><FileUp className="size-4" aria-hidden /> Go to the Library</Link>
        </div>
      ) : (
        <div className="mt-8 grid gap-3 text-left sm:grid-cols-2">
          {STARTERS.map((s) => (
            <PromptSuggestion key={s.title} icon={s.icon} title={s.title} hint={s.hint} onSelect={() => onPick(s)} />
          ))}
        </div>
      )}
    </div>
  );
}
