"use client";

import { useState } from "react";
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
import type { AdminOutreachMessage } from "@/src/lib/types";
import {
  useAdminOutreachMessages,
  useModerateOutreachMessage,
} from "../hooks/useOutreachModeration";

type StatusFilter = "all" | "draft" | "sent";
type BlockedFilter = "all" | "blocked" | "unblocked";

function toStatusParam(filter: StatusFilter): string | null {
  return filter === "all" ? null : filter;
}

function toAdminBlockedParam(filter: BlockedFilter): boolean | null {
  if (filter === "blocked") return true;
  if (filter === "unblocked") return false;
  return null;
}

/**
 * Cursor-paginated outreach moderation list, mirroring UsersTable's
 * cursor-pagination-stack UI and handleToggleStatus's confirm-then-mutate pattern
 * (no page-number UI, since cursor pagination has no stable page count).
 */
export function OutreachModerationPanel() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [blockedFilter, setBlockedFilter] = useState<BlockedFilter>("all");
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);

  const cursor = cursorStack[cursorStack.length - 1];
  const status = toStatusParam(statusFilter);
  const adminBlocked = toAdminBlockedParam(blockedFilter);

  const { data, isLoading } = useAdminOutreachMessages(cursor, { status, adminBlocked });
  const moderate = useModerateOutreachMessage();

  function handleStatusFilterChange(value: string) {
    setStatusFilter(value as StatusFilter);
    setCursorStack([null]);
  }

  function handleBlockedFilterChange(value: string) {
    setBlockedFilter(value as BlockedFilter);
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

  function handleToggleBlocked(message: AdminOutreachMessage) {
    const nextAdminBlocked = !message.adminBlocked;
    const confirmed = window.confirm(
      nextAdminBlocked
        ? `Block outreach message "${message.subject}" to ${message.companyName}?`
        : `Unblock outreach message "${message.subject}" to ${message.companyName}?`,
    );
    if (!confirmed) return;
    moderate.mutate({ id: message.id, adminBlocked: nextAdminBlocked });
  }

  const items = data?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Select value={statusFilter} onValueChange={handleStatusFilterChange}>
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="sent">Sent</SelectItem>
            </SelectContent>
          </Select>
          <Select value={blockedFilter} onValueChange={handleBlockedFilterChange}>
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All messages</SelectItem>
              <SelectItem value="blocked">Blocked</SelectItem>
              <SelectItem value="unblocked">Not blocked</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {!items.length && !isLoading ? (
        <EmptyState
          title="No outreach messages found"
          description="Try a different status or block filter."
        />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead>Subject</TableHead>
                <TableHead>Recipient role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Moderation</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((message) => (
                <TableRow key={message.id}>
                  <TableCell>{message.companyName}</TableCell>
                  <TableCell>{message.subject}</TableCell>
                  <TableCell>{message.recipientRoleTitle ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant={message.status === "sent" ? "success" : "outline"}>
                      {message.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={message.adminBlocked ? "warning" : "outline"}>
                      {message.adminBlocked ? "Blocked" : "Allowed"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={moderate.isPending}
                      onClick={() => handleToggleBlocked(message)}
                    >
                      {message.adminBlocked ? "Unblock" : "Block"}
                    </Button>
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
    </div>
  );
}
