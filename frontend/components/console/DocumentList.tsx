"use client";

import Link from "next/link";
import { useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DocumentStatusBadge } from "@/components/console/DocumentStatusBadge";
import { EmptyState } from "@/components/console/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  formatConsoleTimestamp,
  formatFileSize,
  formatRelativeTime,
} from "@/components/console/formatters";
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

  if (loading && documents.length === 0) {
    return (
      <div className="space-y-3 rounded-xl border border-border/70 bg-surface p-4">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }

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
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-surface p-4">
        <div>
          <p className="text-sm font-medium text-foreground">Uploaded documents</p>
          <p className="text-sm text-muted-foreground">
            {documents.length} file{documents.length === 1 ? "" : "s"} available for review and
            downstream workflows.
          </p>
        </div>
        <Badge variant="outline">{documents.length} tracked</Badge>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Document</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Added</TableHead>
            <TableHead className="w-[220px]">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((doc) => (
            <TableRow key={doc.documentId}>
              <TableCell>
                <div className="min-w-0 space-y-2">
                  <div className="truncate text-sm font-medium text-foreground">
                    <Link
                      href={`/app/documents/${doc.documentId}`}
                      className="text-primary hover:underline"
                    >
                      {doc.originalFilename}
                    </Link>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span>{formatFileSize(doc.fileSizeBytes)}</span>
                    <span className="font-mono">{doc.documentId}</span>
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="outline">
                  {doc.documentType === "cv" ? "CV / resume" : "Cover letter"}
                </Badge>
              </TableCell>
              <TableCell>
                <DocumentStatusBadge status={doc.processingStatus} />
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                <div>{formatRelativeTime(doc.createdAt)}</div>
                <div className="mt-1">{formatConsoleTimestamp(doc.createdAt)}</div>
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-2">
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
