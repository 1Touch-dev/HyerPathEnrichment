"use client";

import Link from "next/link";
import { useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import { DocumentStatusBadge } from "@/components/console/DocumentStatusBadge";
import { EmptyState } from "@/components/console/EmptyState";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDeleteDocument, useReprocessDocument } from "@/features/documents";
import type { CandidateDocument } from "@/src/lib/types";

type DocumentListProps = {
  documents: CandidateDocument[];
  loading?: boolean;
};

export function DocumentList({ documents, loading }: DocumentListProps) {
  const deleteMutation = useDeleteDocument();
  const reprocessMutation = useReprocessDocument();
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  if (!documents.length && !loading) {
    return (
      <EmptyState
        title="No documents yet"
        description="Upload a CV or cover letter above to get started."
      />
    );
  }

  const handleDelete = async (documentId: string) => {
    const confirmed = window.confirm("Delete this document? This cannot be undone.");
    if (!confirmed) return;
    setPendingDeleteId(documentId);
    try {
      await deleteMutation.mutateAsync(documentId);
    } finally {
      setPendingDeleteId(null);
    }
  };

  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Filename</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Created</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((doc) => (
            <TableRow key={doc.documentId}>
              <TableCell>
                <div className="min-w-0">
                  <div className="truncate">
                    <Link
                      href={`/app/documents/${doc.documentId}`}
                      className="text-primary hover:underline"
                    >
                      {doc.originalFilename}
                    </Link>
                  </div>
                  <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                    {doc.documentId}
                  </div>
                </div>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {doc.documentType === "cv" ? "CV" : "Cover letter"}
              </TableCell>
              <TableCell>
                <DocumentStatusBadge status={doc.processingStatus} />
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {formatDate(doc.createdAt)}
              </TableCell>
              <TableCell>
                <div className="flex gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/app/documents/${doc.documentId}`}>View</Link>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={reprocessMutation.isPending}
                    onClick={() => reprocessMutation.mutate(doc.documentId)}
                  >
                    <RefreshCw className="mr-1 size-3" />
                    Reprocess
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={pendingDeleteId === doc.documentId}
                    onClick={() => void handleDelete(doc.documentId)}
                  >
                    <Trash2 className="mr-1 size-3" />
                    Delete
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function formatDate(value: string) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}
