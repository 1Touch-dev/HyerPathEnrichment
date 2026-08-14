"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { fetchDocuments } from "@/src/lib/api-client";

/**
 * Thin list page (§13.2) — upload itself reuses whatever generic upload widget
 * Foundation Week 1 already ships for `POST /api/documents`; this view only lists
 * documents and links into each one's detail page. Fetches through the existing
 * `GET /api/documents` BFF route (added by the outreach reconciliation pass to
 * resolve a document for "Draft outreach"), whose response is a plain array of
 * `DocumentSummary` — not the `{ documents: [...] }` wrapper shape.
 */
export function DocumentsView() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["documents", "list"],
    queryFn: async () => (await fetchDocuments()).data,
  });

  if (isLoading) return <div className="animate-pulse h-96 rounded-lg bg-muted" />;
  if (isError) {
    return (
      <EmptyState title="Couldn't load your documents" description="Please try again shortly." />
    );
  }
  if (!data || data.length === 0) {
    return (
      <EmptyState title="No CV uploaded yet" description="Upload a PDF or DOCX to get started." />
    );
  }

  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold">Your documents</h1>
      {data.map((doc) => (
        <Link
          key={doc.documentId}
          href={`/app/documents/${doc.documentId}`}
          className="flex items-center justify-between rounded-lg border p-4 transition hover:border-primary"
        >
          <span className="font-medium">{doc.originalFilename}</span>
          <Badge variant={doc.processingStatus === "completed" ? "default" : "outline"}>
            {doc.processingStatus}
          </Badge>
        </Link>
      ))}
    </div>
  );
}
