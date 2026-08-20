"use client";

import { useState } from "react";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AdminDocument, AdminDocumentFilters } from "@/src/lib/types";
import { useAdminDocuments, useModerateDocument } from "../hooks/useDocumentsModeration";

type DeletedFilter = "all" | "active" | "deleted";

function toDeleted(filter: DeletedFilter): boolean | null {
  if (filter === "active") return false;
  if (filter === "deleted") return true;
  return null;
}

/**
 * Cursor-paginated documents moderation table, mirroring UsersTable.tsx's
 * cursor-stack pagination and window.confirm-gated destructive action pattern
 * (see handleToggleStatus there) for the soft-delete/restore toggle here.
 */
export function DocumentsModerationPanel() {
  const [deletedFilter, setDeletedFilter] = useState<DeletedFilter>("all");
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);

  const cursor = cursorStack[cursorStack.length - 1];
  const filters: AdminDocumentFilters = {
    processingStatus: null,
    deleted: toDeleted(deletedFilter),
  };

  const { data, isLoading } = useAdminDocuments(cursor, filters);
  const moderateDocument = useModerateDocument();

  function handleFilterChange(value: string) {
    setDeletedFilter(value as DeletedFilter);
    setCursorStack([null]);
  }

  function handleNext() {
    if (data?.nextCursor) {
      setCursorStack((stack) => [...stack, data.nextCursor]);
    }
  }

  function handlePrevious() {
    setCursorStack((stack) => (stack.length > 1 ? stack.slice(0, -1) : stack));
  }

  function handleToggleModeration(document: AdminDocument) {
    const isDeleted = !!document.deletedAt;
    const confirmed = window.confirm(
      isDeleted
        ? `Restore "${document.originalFilename}"?`
        : `Soft-delete "${document.originalFilename}"?`,
    );
    if (!confirmed) return;
    moderateDocument.mutate({
      documentId: document.id,
      action: isDeleted ? "restore" : "soft_delete",
    });
  }

  const items = data?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <Select value={deletedFilter} onValueChange={handleFilterChange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All documents</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="deleted">Deleted</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {!items.length && !isLoading ? (
        <EmptyState title="No documents found" description="Try a different status filter." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Filename</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Processing status</TableHead>
                <TableHead>Moderation</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((document) => (
                <TableRow key={document.id}>
                  <TableCell>{document.originalFilename}</TableCell>
                  <TableCell>{document.documentType}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{document.processingStatus}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={document.deletedAt ? "warning" : "success"}>
                      {document.deletedAt ? "Deleted" : "Active"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={moderateDocument.isPending}
                      onClick={() => handleToggleModeration(document)}
                    >
                      {document.deletedAt ? "Restore" : "Soft-delete"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <div className="flex items-center justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={cursorStack.length <= 1 || isLoading}
          onClick={handlePrevious}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!data?.hasMore || isLoading}
          onClick={handleNext}
        >
          Next page
        </Button>
      </div>
    </div>
  );
}
