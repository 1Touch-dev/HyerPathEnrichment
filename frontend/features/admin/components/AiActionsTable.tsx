"use client";

import { useState } from "react";
import { EmptyState } from "@/components/console/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAiAction, useAiActions } from "../hooks/useAiActions";

// This plan's backend emits a small, stable action-type vocabulary — hardcoded
// here rather than a dedicated dropdown-population endpoint, mirroring
// `AuditLogTable`'s ACTIONS list (§12.4).
const ACTION_TYPES = [
  "outreach_draft_generated",
  "company_tier_classified",
  "candidate_matched",
  "resume_tailored",
];

/**
 * Filterable table of AI-agent actions (audit/oversight view), with row click
 * opening a drill-down detail sheet — composition mirrors `AuditLogTable`'s
 * filter/pagination layout and `ReviewQueueDetail`'s sheet-based drill-down idiom.
 */
export function AiActionsTable() {
  const [actionType, setActionType] = useState<string | null>(null);
  const [candidateId, setCandidateId] = useState("");
  const [recruiterId, setRecruiterId] = useState("");
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const cursor = cursorStack[cursorStack.length - 1];

  const { data, isLoading } = useAiActions(cursor, {
    actionType,
    candidateId: candidateId.trim() || null,
    recruiterId: recruiterId.trim() || null,
  });

  const items = data?.items ?? [];

  function handleActionTypeChange(value: string) {
    setActionType(value === "all" ? null : value);
    setCursorStack([null]);
  }

  function handleCandidateIdChange(value: string) {
    setCandidateId(value);
    setCursorStack([null]);
  }

  function handleRecruiterIdChange(value: string) {
    setRecruiterId(value);
    setCursorStack([null]);
  }

  function handleNext() {
    if (data?.nextCursor) setCursorStack((stack) => [...stack, data.nextCursor]);
  }

  function handlePrevious() {
    setCursorStack((stack) => (stack.length > 1 ? stack.slice(0, -1) : stack));
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-4">
        <Select value={actionType ?? "all"} onValueChange={handleActionTypeChange}>
          <SelectTrigger className="w-[220px]">
            <SelectValue placeholder="All action types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All action types</SelectItem>
            {ACTION_TYPES.map((type) => (
              <SelectItem key={type} value={type}>
                {type}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder="Filter by candidate ID"
          className="w-[220px]"
          value={candidateId}
          onChange={(event) => handleCandidateIdChange(event.target.value)}
        />
        <Input
          placeholder="Filter by recruiter ID"
          className="w-[220px]"
          value={recruiterId}
          onChange={(event) => handleRecruiterIdChange(event.target.value)}
        />
      </div>

      {!items.length && !isLoading ? (
        <EmptyState title="No AI actions" description="Nothing matches this filter yet." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp</TableHead>
                <TableHead>Action type</TableHead>
                <TableHead>Candidate</TableHead>
                <TableHead>Triggered by</TableHead>
                <TableHead>Summary</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow
                  key={item.id}
                  className="cursor-pointer"
                  onClick={() => setSelectedId(item.id)}
                >
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDate(item.createdAt)}
                  </TableCell>
                  <TableCell>{item.actionType}</TableCell>
                  <TableCell className="font-mono text-xs">{item.candidateUserId ?? "—"}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.triggeredByUserId ?? "—"}
                  </TableCell>
                  <TableCell className="max-w-xs truncate">{item.summary ?? "—"}</TableCell>
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
        <AiActionDetail
          actionId={selectedId}
          open
          onOpenChange={(open) => {
            if (!open) setSelectedId(null);
          }}
        />
      ) : null}
    </div>
  );
}

type AiActionDetailProps = {
  actionId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function AiActionDetail({ actionId, open, onOpenChange }: AiActionDetailProps) {
  const { data, isLoading } = useAiAction(actionId);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>AI action</SheetTitle>
          <SheetDescription>{data ? data.actionType : "Loading…"}</SheetDescription>
        </SheetHeader>

        {isLoading || !data ? (
          <p className="mt-6 text-sm text-muted-foreground">Loading…</p>
        ) : (
          <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
            <div className="col-span-2">
              <dt className="text-muted-foreground">Summary</dt>
              <dd>{data.summary ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Candidate</dt>
              <dd className="break-all font-mono text-xs">{data.candidateUserId ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Triggered by</dt>
              <dd className="break-all font-mono text-xs">{data.triggeredByUserId ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Related record</dt>
              <dd className="break-all font-mono text-xs">{data.relatedId ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Created at</dt>
              <dd>{formatDate(data.createdAt)}</dd>
            </div>
          </dl>
        )}
      </SheetContent>
    </Sheet>
  );
}

function formatDate(value: string) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}
