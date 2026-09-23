"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { EmptyState } from "@/components/console/EmptyState";
import { DeskMetricCard, DeskMetricGrid, DeskPagination } from "@/components/desk/desk-shell";
import { Badge } from "@/components/ui/badge";
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
import { fetchAdminUsers } from "../api/client";
import { adminKeys } from "../api/keys";
import { useAuditLogs } from "../hooks/useAuditLogs";
import { DESK_KPI_CARD_CLASS } from "./desk-kpi";

// This plan's backend emits a small, stable action vocabulary — hardcoded
// here rather than a dedicated `GET /audit-logs/actions` dropdown-population
// endpoint (a deliberate smaller-footprint choice, §12.4).
const ACTIONS = [
  "user.status_changed",
  "user.role_changed",
  "feature_flag.flipped",
  "impersonation.started",
  "impersonation.ended",
];

type AuditLogTableProps = {
  /** When set, only rows whose targetId matches are shown (client-side filter
   * of the fetched page — there is no dedicated by-target-id backend filter). */
  targetId?: string;
};

export function AuditLogTable({ targetId }: AuditLogTableProps) {
  const [action, setAction] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const cursor = cursorStack[cursorStack.length - 1];

  const { data, isLoading } = useAuditLogs(cursor, action);
  // Actor emails aren't included on the audit log rows — resolved client-side
  // from a small users lookup (or left as a UUID if not resolvable), per §12.4.
  const usersLookup = useQuery({
    queryKey: adminKeys.users(null, null),
    queryFn: () => fetchAdminUsers(null, null),
  });

  const emailByUserId = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of usersLookup.data?.items ?? []) {
      map.set(item.id, item.email);
    }
    return map;
  }, [usersLookup.data]);

  const items = useMemo(() => {
    const all = data?.items ?? [];
    return targetId ? all.filter((entry) => entry.targetId === targetId) : all;
  }, [data?.items, targetId]);
  const explicitCount = items.filter((entry) => entry.capturedBy === "explicit").length;

  function handleActionChange(value: string) {
    setAction(value === "all" ? null : value);
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
      {targetId ? (
        <SectionHeader>
          <SectionHeaderContent>
            <SectionHeaderTitle className="text-base">
              Audit entries on this page
            </SectionHeaderTitle>
            <SectionHeaderDescription>
              The detail view filters the currently loaded audit slice client-side by target ID.
            </SectionHeaderDescription>
          </SectionHeaderContent>
        </SectionHeader>
      ) : (
        <>
          <DeskMetricGrid className="xl:grid-cols-3">
            <DeskMetricCard
              label="Entries on this page"
              value={items.length}
              hint="Current cursor slice"
              className={DESK_KPI_CARD_CLASS}
            />
            <DeskMetricCard
              label="Explicit captures"
              value={explicitCount}
              hint="Directly recorded admin actions"
              className={DESK_KPI_CARD_CLASS}
            />
            <DeskMetricCard
              label="Filter state"
              value={action ?? "All actions"}
              hint="Known audit vocabulary only"
              className={DESK_KPI_CARD_CLASS}
            />
          </DeskMetricGrid>
          <FilterBar>
            <FilterBarGroup>
              <div className="space-y-2">
                <SectionHeader>
                  <SectionHeaderContent>
                    <SectionHeaderTitle className="text-base">Action filters</SectionHeaderTitle>
                    <SectionHeaderDescription>
                      Filter the current audit feed without altering the stable backend action
                      vocabulary.
                    </SectionHeaderDescription>
                  </SectionHeaderContent>
                </SectionHeader>
                <Select value={action ?? "all"} onValueChange={handleActionChange}>
                  <SelectTrigger className="w-[220px]">
                    <SelectValue placeholder="All actions" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All actions</SelectItem>
                    {ACTIONS.map((a) => (
                      <SelectItem key={a} value={a}>
                        {a}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </FilterBarGroup>
            <FilterBarActions>
              <div className="text-right text-sm text-muted-foreground">
                Actor emails resolve from the current user slice when available.
              </div>
            </FilterBarActions>
          </FilterBar>
        </>
      )}

      {!items.length && !isLoading ? (
        <EmptyState title="No audit log entries" description="Nothing matches this filter yet." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Target</TableHead>
                <TableHead>Captured by</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDate(entry.createdAt)}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {entry.actorUserId
                      ? (emailByUserId.get(entry.actorUserId) ?? entry.actorUserId)
                      : "—"}
                  </TableCell>
                  <TableCell>{entry.action}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {entry.targetType}
                    {entry.targetId ? `:${entry.targetId}` : ""}
                  </TableCell>
                  <TableCell>
                    <Badge variant={entry.capturedBy === "explicit" ? "default" : "secondary"}>
                      {entry.capturedBy}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {targetId ? null : (
        <DeskPagination
          canPrevious={cursorStack.length > 1 && !isLoading}
          canNext={Boolean(data?.hasMore) && !isLoading}
          onPrevious={handlePrevious}
          onNext={handleNext}
        />
      )}
    </div>
  );
}

function formatDate(value: string) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}
