"use client";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
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
              <RoleBadge isSuperuser={user.isSuperuser} roleName={user.roleName} />
            </dd>
            <p className="mt-2 text-xs text-muted-foreground">
              Role assignment is unavailable in Wave 2 until ADR21 `P3` controls are implemented.
            </p>
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
