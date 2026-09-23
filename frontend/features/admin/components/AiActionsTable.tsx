"use client";

import { useState } from "react";
import { EmptyState } from "@/components/console/EmptyState";
import { DeskMetricCard, DeskMetricGrid, DeskPagination } from "@/components/desk/desk-shell";
import { Badge } from "@/components/ui/badge";
import { FilterBar, FilterBarActions, FilterBarGroup } from "@/components/ui/filter-bar";
import { Input } from "@/components/ui/input";
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
import { DESK_KPI_CARD_CLASS } from "./desk-kpi";

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
  const reviewedActions = items.filter((item) => item.summary).length;

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
      <DeskMetricGrid>
        <DeskMetricCard
          label="Actions on this page"
          value={items.length}
          hint="Current cursor slice"
          className={DESK_KPI_CARD_CLASS}
        />
        <DeskMetricCard
          label="Rows with summaries"
          value={reviewedActions}
          hint="Human-readable action context"
          className={DESK_KPI_CARD_CLASS}
        />
        <DeskMetricCard
          label="Action type filter"
          value={actionType ?? "All action types"}
          hint="Stable action vocabulary"
          className={DESK_KPI_CARD_CLASS}
        />
      </DeskMetricGrid>

      <FilterBar>
        <FilterBarGroup>
          <div className="flex flex-1 flex-wrap items-end gap-3 sm:gap-4">
            <div className="space-y-2">
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
            </div>
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
        </FilterBarGroup>
        <FilterBarActions>
          <div className="text-right text-sm text-muted-foreground">
            Select a row to inspect the AI action detail sheet.
          </div>
        </FilterBarActions>
      </FilterBar>

      {!items.length && !isLoading ? (
        <EmptyState title="No AI actions" description="Nothing matches this filter yet." />
      ) : (
        <div className="flex flex-col gap-3">
          <SectionHeader>
            <SectionHeaderContent>
              <SectionHeaderTitle>Oversight feed</SectionHeaderTitle>
              <SectionHeaderDescription>
                Dense action feed for oversight, scoped by candidate, recruiter, and action type.
              </SectionHeaderDescription>
            </SectionHeaderContent>
            <SectionHeaderActions>
              <Badge variant="outline">Click row for detail</Badge>
            </SectionHeaderActions>
          </SectionHeader>
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

      <DeskPagination
        canPrevious={cursorStack.length > 1 && !isLoading}
        canNext={Boolean(data?.hasMore) && !isLoading}
        onPrevious={handlePrevious}
        onNext={handleNext}
      />

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
          <div className="mt-6 flex flex-col gap-6">
            <DeskMetricGrid className="grid-cols-1 sm:grid-cols-2 xl:grid-cols-2">
              <DeskMetricCard
                label="Action type"
                value={data.actionType}
                hint={formatDate(data.createdAt)}
                className={DESK_KPI_CARD_CLASS}
              />
              <DeskMetricCard
                label="Related record"
                value={<span className="break-all font-mono text-xs">{data.relatedId ?? "—"}</span>}
                hint="Best-effort linked record"
                className={DESK_KPI_CARD_CLASS}
              />
            </DeskMetricGrid>

            <section className="rounded-lg border border-border/70 bg-card p-4">
              <SectionHeader>
                <SectionHeaderContent>
                  <SectionHeaderTitle>Action context</SectionHeaderTitle>
                  <SectionHeaderDescription>
                    Operator-facing details for the recorded AI action.
                  </SectionHeaderDescription>
                </SectionHeaderContent>
              </SectionHeader>
              <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
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
                  <dt className="text-muted-foreground">Created at</dt>
                  <dd>{formatDate(data.createdAt)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Related record</dt>
                  <dd className="break-all font-mono text-xs">{data.relatedId ?? "—"}</dd>
                </div>
              </dl>
            </section>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function formatDate(value: string) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}
