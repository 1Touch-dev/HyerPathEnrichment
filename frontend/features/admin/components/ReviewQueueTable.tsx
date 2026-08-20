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
import type { AdminReviewQueueItem } from "@/src/lib/types";
import { useReviewQueue } from "../hooks/useReviewQueue";
import { ReviewQueueDetail } from "./ReviewQueueDetail";

const RESOURCE_TYPES = [
  "job_posting",
  "document",
  "portfolio_item",
  "outreach_message",
  "question",
  "practice_audio",
];

const STATUSES = ["pending", "approved", "rejected"];

function statusBadgeVariant(status: AdminReviewQueueItem["status"]) {
  if (status === "approved") return "success";
  if (status === "rejected") return "destructive";
  return "warning";
}

/**
 * Cursor-paginated review-queue table (same cursor-stack pattern as
 * `UsersTable`, since this router is also cursor-paginated, not offset-based).
 * Selecting a row opens `ReviewQueueDetail` in a drawer, mirroring
 * `UserDetailDrawer`'s sheet-based detail pattern.
 */
export function ReviewQueueTable() {
  const [resourceType, setResourceType] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const cursor = cursorStack[cursorStack.length - 1];
  const { data, isLoading } = useReviewQueue(cursor, resourceType, status);

  function handleResourceTypeChange(value: string) {
    setResourceType(value === "all" ? null : value);
    setCursorStack([null]);
  }

  function handleStatusChange(value: string) {
    setStatus(value === "all" ? null : value);
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

  const items = data?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <Select value={resourceType ?? "all"} onValueChange={handleResourceTypeChange}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="All resource types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All resource types</SelectItem>
            {RESOURCE_TYPES.map((type) => (
              <SelectItem key={type} value={type}>
                {type}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={status ?? "all"} onValueChange={handleStatusChange}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {!items.length && !isLoading ? (
        <EmptyState
          title="No review queue items found"
          description="Try a different resource type or status filter."
        />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Resource type</TableHead>
                <TableHead>Flag reason</TableHead>
                <TableHead>Flag source</TableHead>
                <TableHead>Flagged at</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-mono text-xs">{item.resourceType}</TableCell>
                  <TableCell>{item.flagReason ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{item.flagSource}</Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDate(item.flaggedAt)}
                  </TableCell>
                  <TableCell>
                    <Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>
                  </TableCell>
                  <TableCell>
                    <Button variant="outline" size="sm" onClick={() => setSelectedId(item.id)}>
                      Review
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

      {selectedId ? (
        <ReviewQueueDetail
          itemId={selectedId}
          open
          onOpenChange={(open) => {
            if (!open) setSelectedId(null);
          }}
        />
      ) : null}
    </div>
  );
}

function formatDate(value: string) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}
