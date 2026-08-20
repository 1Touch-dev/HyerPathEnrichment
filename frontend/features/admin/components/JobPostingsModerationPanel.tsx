"use client";

import { useState, type FormEvent } from "react";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
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
import { Textarea } from "@/components/ui/textarea";
import type { AdminJobPosting, ModerationStatus } from "@/src/lib/types";
import type { JobPostingFilters } from "../api/client";
import { useAdminJobPostings, useModerateJobPosting } from "../hooks/useJobPostingsModeration";

type ModerationStatusFilter = "all" | ModerationStatus;

function toFilters(statusFilter: ModerationStatusFilter): JobPostingFilters {
  return statusFilter === "all" ? {} : { moderationStatus: statusFilter };
}

function statusBadgeVariant(status: ModerationStatus): "success" | "warning" | "destructive" {
  if (status === "active") return "success";
  if (status === "hidden") return "warning";
  return "destructive";
}

type PendingModeration = {
  posting: AdminJobPosting;
  nextStatus: ModerationStatus;
};

/**
 * Cursor-paginated job postings moderation list, mirroring UsersTable's
 * cursor-stack pagination (no page-number UI, Decision 4). Restoring a
 * posting to "active" is non-destructive and uses the simple
 * window.confirm pattern from UsersTable's handleToggleStatus; hiding or
 * removing a posting instead opens a small dialog with an optional reason
 * field, since those are the more consequential moderation actions and
 * ModerateJobPostingRequest.reason is captured in the admin audit log's
 * `after` payload (job_postings_router.py's moderate_job_posting).
 */
export function JobPostingsModerationPanel() {
  const [statusFilter, setStatusFilter] = useState<ModerationStatusFilter>("all");
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const [pendingModeration, setPendingModeration] = useState<PendingModeration | null>(null);

  const cursor = cursorStack[cursorStack.length - 1];
  const filters = toFilters(statusFilter);

  const { data, isLoading } = useAdminJobPostings(cursor, filters);
  const moderate = useModerateJobPosting();

  function handleFilterChange(value: string) {
    setStatusFilter(value as ModerationStatusFilter);
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

  function handleRestore(posting: AdminJobPosting) {
    const confirmed = window.confirm(`Restore "${posting.title}" at ${posting.company} to active?`);
    if (!confirmed) return;
    moderate.mutate({ id: posting.id, moderationStatus: "active" });
  }

  function handleRequestModeration(posting: AdminJobPosting, nextStatus: ModerationStatus) {
    setPendingModeration({ posting, nextStatus });
  }

  const items = data?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <Select value={statusFilter} onValueChange={handleFilterChange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="hidden">Hidden</SelectItem>
            <SelectItem value="removed">Removed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {!items.length && !isLoading ? (
        <EmptyState title="No job postings found" description="Try a different status filter." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Company</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((posting) => (
                <TableRow key={posting.id}>
                  <TableCell>{posting.title}</TableCell>
                  <TableCell>{posting.company}</TableCell>
                  <TableCell>{posting.location ?? (posting.remote ? "Remote" : "—")}</TableCell>
                  <TableCell>{posting.source}</TableCell>
                  <TableCell>
                    <Badge variant={statusBadgeVariant(posting.moderationStatus)}>
                      {posting.moderationStatus}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      {posting.moderationStatus !== "active" ? (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={moderate.isPending}
                          onClick={() => handleRestore(posting)}
                        >
                          Restore
                        </Button>
                      ) : null}
                      {posting.moderationStatus !== "hidden" ? (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={moderate.isPending}
                          onClick={() => handleRequestModeration(posting, "hidden")}
                        >
                          Hide
                        </Button>
                      ) : null}
                      {posting.moderationStatus !== "removed" ? (
                        <Button
                          variant="destructive"
                          size="sm"
                          disabled={moderate.isPending}
                          onClick={() => handleRequestModeration(posting, "removed")}
                        >
                          Remove
                        </Button>
                      ) : null}
                    </div>
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

      {pendingModeration ? (
        <ModerateJobPostingDialog
          posting={pendingModeration.posting}
          nextStatus={pendingModeration.nextStatus}
          open
          onOpenChange={(open) => {
            if (!open) setPendingModeration(null);
          }}
        />
      ) : null}
    </div>
  );
}

type ModerateJobPostingDialogProps = {
  posting: AdminJobPosting;
  nextStatus: ModerationStatus;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function ModerateJobPostingDialog({
  posting,
  nextStatus,
  open,
  onOpenChange,
}: ModerateJobPostingDialogProps) {
  const moderate = useModerateJobPosting();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const actionLabel = nextStatus === "hidden" ? "Hide" : "Remove";
  const actioningLabel = nextStatus === "hidden" ? "Hiding" : "Removing";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await moderate.mutateAsync({
        id: posting.id,
        moderationStatus: nextStatus,
        reason: reason.trim() || undefined,
      });
      onOpenChange(false);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : `Failed to ${actionLabel.toLowerCase()} posting.`,
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {actionLabel} &quot;{posting.title}&quot;?
          </DialogTitle>
          <DialogDescription>
            {posting.company} — this action is recorded in the admin audit trail.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="moderation-reason">Reason (optional)</Label>
            <Textarea
              id="moderation-reason"
              placeholder="e.g. Reported as a duplicate listing"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={500}
            />
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant={nextStatus === "removed" ? "destructive" : "default"}
              disabled={moderate.isPending}
            >
              {moderate.isPending ? `${actioningLabel}…` : actionLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
