"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchRoles } from "../api/client";
import { adminKeys } from "../api/keys";
import { useAssignUserRole } from "../hooks/useAdminUsers";
import { AuditLogTable } from "./AuditLogTable";
import { RoleBadge } from "./RoleBadge";
import type { AdminUser } from "@/src/lib/types";

type UserDetailDrawerProps = {
  user: AdminUser;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Sheet-based full profile view, with role assignment and a mini audit-log
 * scoped to this user (reuses AuditLogTable filtered by targetId, §12.4). */
export function UserDetailDrawer({ user, open, onOpenChange }: UserDetailDrawerProps) {
  const rolesQuery = useQuery({ queryKey: adminKeys.roles(), queryFn: fetchRoles });
  const assignRole = useAssignUserRole();
  const [editingRole, setEditingRole] = useState(false);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{user.email}</SheetTitle>
          <SheetDescription>
            {user.firstName} {user.lastName}
          </SheetDescription>
        </SheetHeader>

        <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-muted-foreground">Status</dt>
            <dd>
              <Badge variant={user.isActive ? "success" : "warning"}>
                {user.isActive ? "Active" : "Suspended"}
              </Badge>
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Verified</dt>
            <dd>{user.isVerified ? "Yes" : "No"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">MFA</dt>
            <dd>
              <Badge variant={user.mfaEnabled ? "success" : "outline"}>
                {user.mfaEnabled ? "Enabled" : "Off"}
              </Badge>
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Created</dt>
            <dd>{formatDate(user.createdAt)}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-muted-foreground">Role</dt>
            <dd className="mt-1">
              {editingRole ? (
                <Select
                  defaultValue={user.roleId ?? "none"}
                  onValueChange={(value) => {
                    assignRole.mutate({ userId: user.id, roleId: value === "none" ? null : value });
                    setEditingRole(false);
                  }}
                >
                  <SelectTrigger className="w-[180px]" aria-label="Select role">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No role</SelectItem>
                    {(rolesQuery.data ?? []).map((role) => (
                      <SelectItem key={role.id} value={role.id}>
                        {role.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <button type="button" onClick={() => setEditingRole(true)} className="inline-block">
                  <RoleBadge isSuperuser={user.isSuperuser} roleName={user.roleName} />
                </button>
              )}
            </dd>
          </div>
        </dl>

        <div className="mt-8">
          <h3 className="mb-2 text-sm font-semibold">Recent admin actions on this user</h3>
          <AuditLogTable targetId={user.id} />
        </div>
      </SheetContent>
    </Sheet>
  );
}

function formatDate(value: string) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}
