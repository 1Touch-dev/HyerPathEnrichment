"use client";

import { useState } from "react";
import Link from "next/link";
import { LogIn } from "lucide-react";
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
import { useAuth } from "@/providers/auth-provider";
import { hasPermission } from "@/src/lib/product-doors";
import type { AdminUser } from "@/src/lib/types";
import { useAdminUsers, useUpdateUserStatus } from "../hooks/useAdminUsers";
import { ImpersonateUserDialog } from "./ImpersonateUserDialog";
import { RoleBadge } from "./RoleBadge";

type StatusFilter = "all" | "active" | "suspended";

function toIsActive(filter: StatusFilter): boolean | null {
  if (filter === "active") return true;
  if (filter === "suspended") return false;
  return null;
}

/**
 * Cursor-paginated users table. There is no page-number UI (cursor pagination
 * has no stable page count, Decision 4) — instead we keep a small stack of
 * previously-seen cursors so "Previous" is possible without re-deriving one.
 */
export function UsersTable() {
  const { user: currentUser } = useAuth();
  const canImpersonate = hasPermission(currentUser, {
    resource: "impersonation",
    action: "start",
  });
  const canReactivate = hasPermission(currentUser, {
    resource: "users",
    action: "suspend",
  });

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const [impersonateTarget, setImpersonateTarget] = useState<AdminUser | null>(null);

  const cursor = cursorStack[cursorStack.length - 1];
  const isActive = toIsActive(statusFilter);

  const { data, isLoading } = useAdminUsers(cursor, isActive);
  const updateStatus = useUpdateUserStatus();

  function handleFilterChange(value: string) {
    setStatusFilter(value as StatusFilter);
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

  function handleReactivate(targetUser: AdminUser) {
    const confirmed = window.confirm(`Reactivate ${targetUser.email}?`);
    if (!confirmed) return;
    updateStatus.mutate({ userId: targetUser.id, isActive: true });
  }

  const items = data?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        User deactivation is temporarily unavailable until ADR21 typed confirmation and step-up
        controls are implemented.
      </p>
      <div className="flex items-center justify-between gap-4">
        <Select value={statusFilter} onValueChange={handleFilterChange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All users</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="suspended">Suspended</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {!items.length && !isLoading ? (
        <EmptyState title="No users found" description="Try a different status filter." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>MFA</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((targetUser) => (
                <TableRow key={targetUser.id}>
                  <TableCell>
                    <Link
                      href={`/desk/users/${targetUser.id}`}
                      className="text-primary hover:underline"
                    >
                      {targetUser.email}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {targetUser.firstName} {targetUser.lastName}
                  </TableCell>
                  <TableCell>
                    <Badge variant={targetUser.isActive ? "success" : "warning"}>
                      {targetUser.isActive ? "Active" : "Suspended"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <RoleBadge
                      isSuperuser={targetUser.isSuperuser}
                      roleName={targetUser.roleName}
                    />
                  </TableCell>
                  <TableCell>
                    <Badge variant={targetUser.mfaEnabled ? "success" : "outline"}>
                      {targetUser.mfaEnabled ? "Enabled" : "Off"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      {!targetUser.isActive && canReactivate ? (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={updateStatus.isPending}
                          onClick={() => handleReactivate(targetUser)}
                        >
                          Reactivate
                        </Button>
                      ) : null}
                      {canImpersonate ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setImpersonateTarget(targetUser)}
                        >
                          <LogIn className="mr-1 size-3" />
                          Log in as
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

      {impersonateTarget ? (
        <ImpersonateUserDialog
          user={impersonateTarget}
          open
          onOpenChange={(open) => {
            if (!open) setImpersonateTarget(null);
          }}
        />
      ) : null}
    </div>
  );
}
