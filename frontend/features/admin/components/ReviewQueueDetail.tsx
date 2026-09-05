"use client";

import { useState } from "react";
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
            <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-muted-foreground">Status</dt>
                <dd>
                  <Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Flag source</dt>
                <dd>
                  <Badge variant="outline">{item.flagSource}</Badge>
                </dd>
              </div>
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

            <div className="mt-6">
              <h3 className="mb-2 text-sm font-semibold">Resource preview</h3>
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

            <div className="mt-8 flex flex-col gap-3 border-t pt-6">
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
