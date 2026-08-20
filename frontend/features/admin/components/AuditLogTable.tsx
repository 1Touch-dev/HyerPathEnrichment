"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
import { fetchAdminUsers } from "../api/client";
import { adminKeys } from "../api/keys";
import { useAuditLogs } from "../hooks/useAuditLogs";

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
      {targetId ? null : (
        <div className="flex items-center gap-4">
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
      )}
    </div>
  );
}

function formatDate(value: string) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}
