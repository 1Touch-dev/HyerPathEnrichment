"use client";

import { useState } from "react";
import { EmptyState } from "@/components/console/EmptyState";
import { DeskMetricCard, DeskMetricGrid, DeskPagination } from "@/components/desk/desk-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FilterBar, FilterBarActions, FilterBarGroup } from "@/components/ui/filter-bar";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  SectionHeader,
  SectionHeaderActions,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderTitle,
} from "@/components/ui/section-header";
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
  const pendingReviews = items.filter((item) => item.status === "pending").length;
  const approvedReviews = items.filter((item) => item.status === "approved").length;
  const rejectedReviews = items.filter((item) => item.status === "rejected").length;

  return (
    <div className="flex flex-col gap-4">
      <DeskMetricGrid>
        <DeskMetricCard
          label="Items on this page"
          value={items.length}
          hint="Current cursor slice"
        />
        <DeskMetricCard
          label="Pending reviews"
          value={pendingReviews}
          hint={`${approvedReviews} approved / ${rejectedReviews} rejected on this page`}
          tone={pendingReviews > 0 ? "warning" : "success"}
        />
        <DeskMetricCard
          label="Resource filter"
          value={resourceType ?? "All resource types"}
          hint={status ?? "All statuses"}
        />
      </DeskMetricGrid>

      <FilterBar>
        <FilterBarGroup>
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
        </FilterBarGroup>
        <FilterBarActions>
          <div className="text-right text-sm text-muted-foreground">
            Open a row to review the resolved resource and submit the moderation decision.
          </div>
        </FilterBarActions>
      </FilterBar>

      {!items.length && !isLoading ? (
        <EmptyState
          title="No review queue items found"
          description="Try a different resource type or status filter."
        />
      ) : (
        <div className="flex flex-col gap-3">
          <SectionHeader>
            <SectionHeaderContent>
              <SectionHeaderTitle>Moderation queue</SectionHeaderTitle>
              <SectionHeaderDescription>
                Review flagged resources with explicit status, source, and timestamp context.
              </SectionHeaderDescription>
            </SectionHeaderContent>
            <SectionHeaderActions>
              <Badge variant="outline">Backend-enforced decisions</Badge>
            </SectionHeaderActions>
          </SectionHeader>
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

      <DeskPagination
        canPrevious={cursorStack.length > 1 && !isLoading}
        canNext={Boolean(data?.hasMore) && !isLoading}
        onPrevious={handlePrevious}
        onNext={handleNext}
      />

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
