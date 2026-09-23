"use client";

import { useState } from "react";
import { EmptyState } from "@/components/console/EmptyState";
import { DeskMetricCard, DeskMetricGrid } from "@/components/desk/desk-shell";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { FilterBar, FilterBarActions, FilterBarGroup } from "@/components/ui/filter-bar";
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
import type { LinkedInSendBatch, LinkedInSendTask } from "@/src/lib/types";
import {
  useClaimLinkedInTask,
  useCompleteLinkedInTask,
  useCreateLinkedInSendBatch,
  useLinkedInTasks,
  useSkipLinkedInTask,
  useStartLinkedInSendBatch,
} from "../hooks/useLinkedInSendTasks";
import { DESK_KPI_CARD_CLASS } from "./desk-kpi";

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
  const claimedTasks = tasks.filter((task) => task.status === "claimed").length;
  const completedTasks = tasks.filter((task) => task.status === "completed").length;
  const skippedTasks = tasks.filter((task) => task.status === "skipped").length;

  return (
    <div className="flex flex-col gap-4">
      <Alert variant="info">
        <AlertTitle>Human-in-the-loop execution only</AlertTitle>
        <AlertDescription>
          Operators still perform every LinkedIn action manually in their own session. This Desk
          surface only manages task state, batching, and outcome notes.
        </AlertDescription>
      </Alert>

      <DeskMetricGrid>
        <DeskMetricCard
          label="Tasks in current view"
          value={tasks.length}
          hint={`${unbatchedPendingTasks.length} unbatched pending task(s)`}
          className={DESK_KPI_CARD_CLASS}
        />
        <DeskMetricCard
          label="Claimed tasks on page"
          value={claimedTasks}
          hint={`${completedTasks} completed / ${skippedTasks} skipped`}
          className={DESK_KPI_CARD_CLASS}
        />
        <DeskMetricCard
          label="Selected for batching"
          value={selectedTaskIds.size}
          hint="Only pending unbatched tasks are selectable"
          className={DESK_KPI_CARD_CLASS}
        />
      </DeskMetricGrid>

      <FilterBar>
        <FilterBarGroup>
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
        </FilterBarGroup>
        <FilterBarActions>
          <Button
            variant="outline"
            disabled={selectedTaskIds.size === 0}
            onClick={() => setBatchDialogOpen(true)}
          >
            Create batch from selected ({selectedTaskIds.size})
          </Button>
        </FilterBarActions>
      </FilterBar>

      {lastCreatedBatch ? (
        <div className="flex flex-col gap-3 rounded-lg border border-border/70 bg-card p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
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
        <div className="flex flex-col gap-3">
          <SectionHeader>
            <SectionHeaderContent>
              <SectionHeaderTitle>Send queue</SectionHeaderTitle>
              <SectionHeaderDescription>
                Claim, complete, or skip tasks after the operator performs the action manually on
                LinkedIn.
              </SectionHeaderDescription>
            </SectionHeaderContent>
            <SectionHeaderActions>
              <Badge variant="outline">No LinkedIn automation</Badge>
            </SectionHeaderActions>
          </SectionHeader>
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
      <DialogContent className="gap-0 overflow-hidden border-border/70 p-0 sm:max-w-md">
        <div className="border-b border-border/60 bg-primary-soft/50 px-6 py-5">
          <DialogHeader className="space-y-2 text-left">
            <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-primary">
              LinkedIn batch
            </p>
            <DialogTitle>Create LinkedIn send batch</DialogTitle>
            <DialogDescription>
              {selectedCount} of {availablePendingCount} unbatched pending task(s) selected.
              `maxSendsPerDay` is a hard per-day ceiling for this Multilogin profile — the batch
              halts once it&rsquo;s reached and resumes the next day. Creating a batch does not
              start it; you must start it separately.
            </DialogDescription>
          </DialogHeader>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 bg-card px-6 py-5">
          <div className="space-y-2">
            <Label htmlFor="batch-profile-id">Multilogin profile ID</Label>
            <Input
              id="batch-profile-id"
              placeholder="profile-123"
              value={multiloginProfileId}
              onChange={(e) => setMultiloginProfileId(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
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
