"use client";

import { useState } from "react";
import Link from "next/link";
import { LogIn } from "lucide-react";
import { EmptyState } from "@/components/console/EmptyState";
import { DeskMetricCard, DeskMetricGrid, DeskPagination } from "@/components/desk/desk-shell";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  const activeUsersOnPage = items.filter((targetUser) => targetUser.isActive).length;
  const suspendedUsersOnPage = items.length - activeUsersOnPage;

  return (
    <div className="flex flex-col gap-4">
      <Alert variant="warning">
        <AlertTitle>Mutation guardrails remain in force</AlertTitle>
        <AlertDescription>
          User deactivation is temporarily unavailable until ADR21 typed confirmation and step-up
          controls are implemented.
        </AlertDescription>
      </Alert>

      <DeskMetricGrid>
        <DeskMetricCard
          label="Users on this page"
          value={items.length}
          hint="Current cursor slice"
        />
        <DeskMetricCard
          label="Active users on page"
          value={activeUsersOnPage}
          hint="Available for normal app access"
          tone="success"
        />
        <DeskMetricCard
          label="Suspended users on page"
          value={suspendedUsersOnPage}
          hint="Shown when the current filter includes suspended users"
          tone={suspendedUsersOnPage > 0 ? "warning" : "default"}
        />
        <DeskMetricCard
          label="Operator capabilities"
          value={canImpersonate ? "Impersonation enabled" : "Read-only"}
          hint={canReactivate ? "Reactivation allowed" : "Reactivation restricted"}
          tone={canImpersonate || canReactivate ? "info" : "default"}
        />
      </DeskMetricGrid>

      <FilterBar>
        <FilterBarGroup>
          <div className="space-y-2">
            <SectionHeader>
              <SectionHeaderContent>
                <SectionHeaderTitle className="text-base">Account filters</SectionHeaderTitle>
                <SectionHeaderDescription>
                  Cursor pagination stays intact; filters reset to the first slice instead of
                  inventing page numbers.
                </SectionHeaderDescription>
              </SectionHeaderContent>
            </SectionHeader>
            <Select value={statusFilter} onValueChange={handleFilterChange}>
              <SelectTrigger className="w-[180px]" aria-label="Filter by account status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All users</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="suspended">Suspended</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </FilterBarGroup>
        <FilterBarActions>
          <div className="text-right text-sm text-muted-foreground">
            Open a user to inspect role, MFA, and recent admin actions in the detail drawer.
          </div>
        </FilterBarActions>
      </FilterBar>

      {!items.length && !isLoading ? (
        <EmptyState title="No users found" description="Try a different status filter." />
      ) : (
        <div className="flex flex-col gap-3">
          <SectionHeader>
            <SectionHeaderContent>
              <SectionHeaderTitle>Account roster</SectionHeaderTitle>
              <SectionHeaderDescription>
                Dense operational view of account status, role posture, MFA readiness, and safe
                impersonation entrypoints.
              </SectionHeaderDescription>
            </SectionHeaderContent>
            <SectionHeaderActions>
              <Badge variant="outline">Cursor pagination</Badge>
            </SectionHeaderActions>
          </SectionHeader>
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

      <DeskPagination
        canPrevious={cursorStack.length > 1 && !isLoading}
        canNext={Boolean(data?.hasMore) && !isLoading}
        onPrevious={handlePrevious}
        onNext={handleNext}
      />

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
