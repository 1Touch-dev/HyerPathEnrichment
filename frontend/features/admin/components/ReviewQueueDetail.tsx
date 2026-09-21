"use client";

import { useState } from "react";
import { DeskMetricCard, DeskMetricGrid } from "@/components/desk/desk-shell";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  SectionHeader,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderTitle,
} from "@/components/ui/section-header";
import { Textarea } from "@/components/ui/textarea";
import { useDecideReviewQueueItem, useReviewQueueItem } from "../hooks/useReviewQueue";

type ReviewQueueDetailProps = {
  itemId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

type DecideChoice = "approved" | "rejected";

function statusBadgeVariant(status: string) {
  if (status === "approved") return "success";
  if (status === "rejected") return "destructive";
  return "warning";
}

/**
 * Sheet-based detail view for a single review-queue item, with the approve/reject
 * decide action (§`content_review:decide` — the backend, not this component,
 * enforces the permission; see `UsersTable`'s superuser-gated affordances for
 * why this repo has no separate client-side permission list).
 */
export function ReviewQueueDetail({ itemId, open, onOpenChange }: ReviewQueueDetailProps) {
  const { data, isLoading } = useReviewQueueItem(itemId);
  const decide = useDecideReviewQueueItem();

  const [choice, setChoice] = useState<DecideChoice>("approved");
  const [notes, setNotes] = useState("");

  function handleDecide() {
    decide.mutate(
      { id: itemId, status: choice, reviewNotes: notes.trim() || undefined },
      {
        onSuccess: () => onOpenChange(false),
      },
    );
  }

  const item = data?.item;
  const resolvedResource = data?.resolvedResource;
  const alreadyDecided = item ? item.status !== "pending" : false;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Review queue item</SheetTitle>
          <SheetDescription>{item ? item.resourceType : "Loading…"}</SheetDescription>
        </SheetHeader>

        {isLoading || !item ? (
          <p className="mt-6 text-sm text-muted-foreground">Loading…</p>
        ) : (
          <>
            <div className="mt-6 flex flex-col gap-6">
              <DeskMetricGrid className="grid-cols-1 sm:grid-cols-2">
                <DeskMetricCard
                  label="Decision status"
                  value={<Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>}
                  hint={`Flagged ${formatDate(item.flaggedAt)}`}
                  tone={
                    item.status === "approved"
                      ? "success"
                      : item.status === "rejected"
                        ? "danger"
                        : "warning"
                  }
                />
                <DeskMetricCard
                  label="Flag source"
                  value={<Badge variant="outline">{item.flagSource}</Badge>}
                  hint={item.resourceType}
                  tone="info"
                />
              </DeskMetricGrid>

              <section className="rounded-lg border border-border/70 bg-surface p-4">
                <SectionHeader>
                  <SectionHeaderContent>
                    <SectionHeaderTitle>Review context</SectionHeaderTitle>
                    <SectionHeaderDescription>
                      Backend permission checks still decide whether this action is allowed.
                    </SectionHeaderDescription>
                  </SectionHeaderContent>
                </SectionHeader>
                <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
                  <div className="col-span-2">
                    <dt className="text-muted-foreground">Flag reason</dt>
                    <dd>{item.flagReason ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Flagged at</dt>
                    <dd>{formatDate(item.flaggedAt)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Resource ID</dt>
                    <dd className="break-all font-mono text-xs">{item.resourceId}</dd>
                  </div>
                  {item.reviewedAt ? (
                    <>
                      <div>
                        <dt className="text-muted-foreground">Reviewed at</dt>
                        <dd>{formatDate(item.reviewedAt)}</dd>
                      </div>
                      <div className="col-span-2">
                        <dt className="text-muted-foreground">Review notes</dt>
                        <dd>{item.reviewNotes ?? "—"}</dd>
                      </div>
                    </>
                  ) : null}
                </dl>
              </section>

              <div>
                <SectionHeader className="mb-3">
                  <SectionHeaderContent>
                    <SectionHeaderTitle>Resource preview</SectionHeaderTitle>
                    <SectionHeaderDescription>
                      Best-effort resolved payload for human review. Missing previews stay honest.
                    </SectionHeaderDescription>
                  </SectionHeaderContent>
                </SectionHeader>
                {resolvedResource ? (
                  <pre className="max-h-64 overflow-auto rounded-md border bg-muted p-3 text-xs">
                    {JSON.stringify(resolvedResource, null, 2)}
                  </pre>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No resource preview available (deleted, or not yet resolvable for this resource
                    type).
                  </p>
                )}
              </div>

              <Alert variant="info">
                <AlertTitle>
                  {alreadyDecided ? "Re-decide carefully" : "Decision required"}
                </AlertTitle>
                <AlertDescription>
                  Human moderation remains the gate here. Keep notes concise and tied to the
                  decision rationale.
                </AlertDescription>
              </Alert>

              <div className="flex flex-col gap-3 border-t pt-6">
                <h3 className="text-sm font-semibold">{alreadyDecided ? "Re-decide" : "Decide"}</h3>
                <Select value={choice} onValueChange={(value) => setChoice(value as DecideChoice)}>
                  <SelectTrigger className="w-[180px]" aria-label="Decision">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="approved">Approve</SelectItem>
                    <SelectItem value="rejected">Reject</SelectItem>
                  </SelectContent>
                </Select>
                <Textarea
                  placeholder="Review notes (optional)"
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                />
                <Button onClick={handleDecide} disabled={decide.isPending} className="self-start">
                  Submit decision
                </Button>
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}
