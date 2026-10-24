import { Link } from "react-router-dom";
import { plural } from "@/lib/format";
import type { StudyDocument } from "@/types/api";

interface Props {
  documents: StudyDocument[]; // indexed documents only
  selected: string[];
  onChange: (ids: string[]) => void;
  legend?: string;
}

export default function DocumentPicker({ documents, selected, onChange, legend = "Documents" }: Props) {
  if (documents.length === 0) {
    return (
      <p className="rounded-md bg-paper px-3 py-2 text-sm text-muted">
        No indexed documents yet. <Link to="/library" className="font-medium text-accent underline">Upload some in the Library</Link>.
      </p>
    );
  }
  const toggle = (id: string) => onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]);
  return (
    <fieldset>
      <legend className="mb-1.5 flex w-full items-center justify-between text-sm font-medium">
        <span>{legend}</span>
        <span className="text-xs font-normal text-muted">
          {plural(selected.length, "selected", "selected")}{" · "}
          <button type="button" className="underline" onClick={() => onChange(documents.map((d) => d.id))}>all</button>{" / "}
          <button type="button" className="underline" onClick={() => onChange([])}>none</button>
        </span>
      </legend>
      <div className="max-h-48 space-y-1 overflow-y-auto rounded-md border border-line bg-surface p-2">
        {documents.map((d) => (
          <label key={d.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-paper">
            <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} />
            <span className="min-w-0 flex-1 truncate">{d.filename}</span>
            {d.page_count != null && <span className="text-xs text-muted">{plural(d.page_count, "page")}</span>}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
