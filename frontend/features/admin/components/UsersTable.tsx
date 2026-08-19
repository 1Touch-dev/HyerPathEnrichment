"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { LogIn, ShieldCheck } from "lucide-react";
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
import type { AdminUser } from "@/src/lib/types";
import { fetchRoles } from "../api/client";
import { adminKeys } from "../api/keys";
import { useAdminUsers, useAssignUserRole, useUpdateUserStatus } from "../hooks/useAdminUsers";
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
  const isCurrentUserSuperuser = !!currentUser?.is_superuser;
  // impersonation:start is granted to the "admin" role and to superusers
  // (Decision 1's ROLE_PERMISSIONS seed) — the frontend has no per-user
  // permission list, only isSuperuser/roleName, so this mirrors that seed.
  const canImpersonate = isCurrentUserSuperuser || currentUser?.role_name === "admin";

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const [editingRoleUserId, setEditingRoleUserId] = useState<string | null>(null);
  const [impersonateTarget, setImpersonateTarget] = useState<AdminUser | null>(null);

  const cursor = cursorStack[cursorStack.length - 1];
  const isActive = toIsActive(statusFilter);

  const { data, isLoading } = useAdminUsers(cursor, isActive);
  const rolesQuery = useQuery({ queryKey: adminKeys.roles(), queryFn: fetchRoles });
  const updateStatus = useUpdateUserStatus();
  const assignRole = useAssignUserRole();

  const roleOptions = useMemo(() => rolesQuery.data ?? [], [rolesQuery.data]);

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

  function handleToggleStatus(targetUser: AdminUser) {
    const nextIsActive = !targetUser.isActive;
    const confirmed = window.confirm(
      nextIsActive ? `Reactivate ${targetUser.email}?` : `Suspend ${targetUser.email}?`,
    );
    if (!confirmed) return;
    updateStatus.mutate({ userId: targetUser.id, isActive: nextIsActive });
  }

  function handleAssignRole(targetUser: AdminUser, roleId: string) {
    assignRole.mutate({ userId: targetUser.id, roleId: roleId === "none" ? null : roleId });
    setEditingRoleUserId(null);
  }

  const items = data?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
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
                      href={`/app/admin/users/${targetUser.id}`}
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
                    {editingRoleUserId === targetUser.id ? (
                      <Select
                        defaultValue={targetUser.roleId ?? "none"}
                        onValueChange={(value) => handleAssignRole(targetUser, value)}
                      >
                        <SelectTrigger className="w-[140px]" aria-label="Select role">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">No role</SelectItem>
                          {roleOptions.map((role) => (
                            <SelectItem key={role.id} value={role.id}>
                              {role.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <RoleBadge isSuperuser={targetUser.isSuperuser} roleName={targetUser.roleName} />
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={targetUser.mfaEnabled ? "success" : "outline"}>
                      {targetUser.mfaEnabled ? "Enabled" : "Off"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={updateStatus.isPending}
                        onClick={() => handleToggleStatus(targetUser)}
                      >
                        {targetUser.isActive ? "Suspend" : "Reactivate"}
                      </Button>
                      {isCurrentUserSuperuser ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            setEditingRoleUserId((current) =>
                              current === targetUser.id ? null : targetUser.id,
                            )
                          }
                        >
                          <ShieldCheck className="mr-1 size-3" />
                          Assign role
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
