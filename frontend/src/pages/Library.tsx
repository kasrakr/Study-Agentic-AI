import { Library as LibraryIcon, RefreshCw } from "lucide-react";
import DocumentList from "@/components/documents/DocumentList";
import UploadZone from "@/components/documents/UploadZone";
import { Button } from "@/components/ui/Button";
import { EmptyState, Notice, PageHeader, Spinner } from "@/components/ui/feedback";
import { useDocuments } from "@/hooks/useDocuments";

export default function Library() {
  const docs = useDocuments();

  return (
    <div>
      <PageHeader title="Library">
        Upload your lecture notes, slides and readings. Everything you ask, quiz or review is based on these files.
      </PageHeader>

      <UploadZone onUploaded={docs.reload} />

      <section className="mt-8" aria-labelledby="docs-heading">
        <div className="mb-3 flex items-center justify-between">
          <h2 id="docs-heading" className="font-display text-xl font-semibold">Your documents</h2>
          <Button variant="ghost" size="sm" onClick={docs.reload}><RefreshCw className="size-3.5" aria-hidden /> Refresh</Button>
        </div>

        {docs.status === "loading" && <Spinner label="Loading documents…" />}
        {docs.status === "error" && <Notice tone="error" title="Couldn’t load your documents">{docs.error.message}</Notice>}
        {docs.status === "success" && docs.data.documents.length === 0 && (
          <EmptyState icon={LibraryIcon} title="No documents yet">
            Upload a PDF, text or Markdown file above. It’s split into passages and indexed so answers can cite the exact page.
          </EmptyState>
        )}
        {docs.status === "success" && docs.data.documents.length > 0 && (
          <DocumentList documents={docs.data.documents} onChanged={docs.reload} />
        )}
      </section>
    </div>
  );
}
