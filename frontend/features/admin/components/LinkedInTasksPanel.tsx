"use client";

import { useState } from "react";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
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
import type { LinkedInSendBatch, LinkedInSendTask } from "@/src/lib/types";
import {
  useClaimLinkedInTask,
  useCompleteLinkedInTask,
  useCreateLinkedInSendBatch,
  useLinkedInTasks,
  useSkipLinkedInTask,
  useStartLinkedInSendBatch,
} from "../hooks/useLinkedInSendTasks";

type StatusFilter = "all" | "pending" | "claimed" | "completed" | "skipped";

function statusBadgeVariant(status: LinkedInSendTask["status"]) {
  if (status === "completed") return "success" as const;
  if (status === "skipped") return "warning" as const;
  return "outline" as const;
}

/**
 * Human-in-the-loop LinkedIn send task queue (machine-2/06). Operators claim a
 * task, go perform the action themselves on linkedin.com, then mark it
 * complete/skipped here — this UI never automates any click against linkedin.com
 * (see backend/app/modules/outreach/linkedin_send_service.py's module docstring
 * for the legal-risk rationale). The "create batch" flow below only creates the
 * data-model row and starts the rate-limit-enforcing worker skeleton; it does not
 * perform sends either (see backend/app/workers/tasks/linkedin_send_batch.py).
 */
export function LinkedInTasksPanel() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("pending");
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set());
  const [batchDialogOpen, setBatchDialogOpen] = useState(false);
  const [lastCreatedBatch, setLastCreatedBatch] = useState<LinkedInSendBatch | null>(null);

  const status = statusFilter === "all" ? null : statusFilter;
  const { data: tasks = [], isLoading } = useLinkedInTasks(status);
  const claimTask = useClaimLinkedInTask();
  const completeTask = useCompleteLinkedInTask();
  const skipTask = useSkipLinkedInTask();
  const createBatch = useCreateLinkedInSendBatch();
  const startBatch = useStartLinkedInSendBatch();

  function toggleSelected(taskId: string) {
    setSelectedTaskIds((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }

  function handleClaim(task: LinkedInSendTask) {
    claimTask.mutate(task.id);
  }

  function handleComplete(task: LinkedInSendTask) {
    const outcomeNote = window.prompt(
      "Outcome note (optional) — confirm you performed this action yourself on linkedin.com:",
      "",
    );
    if (outcomeNote === null) return;
    completeTask.mutate({ taskId: task.id, outcomeNote: outcomeNote || null });
  }

  function handleSkip(task: LinkedInSendTask) {
    const outcomeNote = window.prompt("Reason for skipping (optional):", "");
    if (outcomeNote === null) return;
    skipTask.mutate({ taskId: task.id, outcomeNote: outcomeNote || null });
  }

  async function handleCreateAndStartBatch(multiloginProfileId: string, maxSendsPerDay: number) {
    const batch = await createBatch.mutateAsync({
      multiloginProfileId,
      maxSendsPerDay,
      taskIds: Array.from(selectedTaskIds),
    });
    setLastCreatedBatch(batch);
    setSelectedTaskIds(new Set());
    setBatchDialogOpen(false);
  }

  function handleStartBatch(batchId: string) {
    startBatch.mutate(batchId, {
      onSuccess: (batch) => setLastCreatedBatch(batch),
    });
  }

  const unbatchedPendingTasks = tasks.filter(
    (task) => task.batchId === null && task.status === "pending",
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <Select
          value={statusFilter}
          onValueChange={(value) => setStatusFilter(value as StatusFilter)}
        >
          <SelectTrigger className="w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="claimed">Claimed</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="skipped">Skipped</SelectItem>
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          disabled={selectedTaskIds.size === 0}
          onClick={() => setBatchDialogOpen(true)}
        >
          Create batch from selected ({selectedTaskIds.size})
        </Button>
      </div>

      {lastCreatedBatch ? (
        <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium">
              Batch {lastCreatedBatch.id.slice(0, 8)} — profile{" "}
              {lastCreatedBatch.multiloginProfileId}
            </p>
            <p className="text-sm text-muted-foreground">
              Status: {lastCreatedBatch.status} · max {lastCreatedBatch.maxSendsPerDay} sends/day
            </p>
          </div>
          {lastCreatedBatch.status === "pending" ? (
            <Button
              size="sm"
              disabled={startBatch.isPending}
              onClick={() => handleStartBatch(lastCreatedBatch.id)}
            >
              Start batch
            </Button>
          ) : null}
        </div>
      ) : null}

      {!tasks.length && !isLoading ? (
        <EmptyState
          title="No LinkedIn tasks found"
          description="Try a different status filter, or wait for candidates to request LinkedIn outreach."
        />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>Profile</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Batch</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tasks.map((task) => (
                <TableRow key={task.id}>
                  <TableCell>
                    <Checkbox
                      checked={selectedTaskIds.has(task.id)}
                      disabled={task.batchId !== null || task.status !== "pending"}
                      onCheckedChange={() => toggleSelected(task.id)}
                    />
                  </TableCell>
                  <TableCell>
                    <a
                      href={task.linkedinProfileUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary underline"
                    >
                      {task.linkedinProfileUrl}
                    </a>
                  </TableCell>
                  <TableCell>{task.actionType.replace(/_/g, " ")}</TableCell>
                  <TableCell>
                    <Badge variant={statusBadgeVariant(task.status)}>{task.status}</Badge>
                  </TableCell>
                  <TableCell>{task.batchId ? task.batchId.slice(0, 8) : "—"}</TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      {task.status === "pending" ? (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={claimTask.isPending}
                          onClick={() => handleClaim(task)}
                        >
                          Claim
                        </Button>
                      ) : null}
                      {task.status === "pending" || task.status === "claimed" ? (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={completeTask.isPending}
                            onClick={() => handleComplete(task)}
                          >
                            Mark sent
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={skipTask.isPending}
                            onClick={() => handleSkip(task)}
                          >
                            Skip
                          </Button>
                        </>
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <CreateBatchDialog
        open={batchDialogOpen}
        onOpenChange={setBatchDialogOpen}
        selectedCount={selectedTaskIds.size}
        availablePendingCount={unbatchedPendingTasks.length}
        isSubmitting={createBatch.isPending}
        onSubmit={handleCreateAndStartBatch}
      />
    </div>
  );
}

type CreateBatchDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedCount: number;
  availablePendingCount: number;
  isSubmitting: boolean;
  onSubmit: (multiloginProfileId: string, maxSendsPerDay: number) => Promise<void>;
};

function CreateBatchDialog({
  open,
  onOpenChange,
  selectedCount,
  availablePendingCount,
  isSubmitting,
  onSubmit,
}: CreateBatchDialogProps) {
  const [multiloginProfileId, setMultiloginProfileId] = useState("");
  const [maxSendsPerDay, setMaxSendsPerDay] = useState("");
  const [error, setError] = useState<string | null>(null);

  const parsedMaxSends = Number(maxSendsPerDay);
  const canSubmit =
    multiloginProfileId.trim().length > 0 && Number.isInteger(parsedMaxSends) && parsedMaxSends > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    try {
      await onSubmit(multiloginProfileId.trim(), parsedMaxSends);
      setMultiloginProfileId("");
      setMaxSendsPerDay("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create batch.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create LinkedIn send batch</DialogTitle>
          <DialogDescription>
            {selectedCount} of {availablePendingCount} unbatched pending task(s) selected.
            `maxSendsPerDay` is a hard per-day ceiling for this Multilogin profile — the batch halts
            once it&rsquo;s reached and resumes the next day. Creating a batch does not start it;
            you must start it separately.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="batch-profile-id">Multilogin profile ID</Label>
            <Input
              id="batch-profile-id"
              placeholder="profile-123"
              value={multiloginProfileId}
              onChange={(e) => setMultiloginProfileId(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="batch-max-sends">Max sends per day</Label>
            <Input
              id="batch-max-sends"
              type="number"
              min={1}
              placeholder="10"
              value={maxSendsPerDay}
              onChange={(e) => setMaxSendsPerDay(e.target.value)}
              required
            />
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit || isSubmitting}>
              {isSubmitting ? "Creating…" : "Create batch"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
