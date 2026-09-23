"use client";

import { DeskMetricCard, DeskMetricGrid } from "@/components/desk/desk-shell";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import {
  SectionHeader,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderTitle,
} from "@/components/ui/section-header";
import { AuditLogTable } from "./AuditLogTable";
import { DESK_KPI_CARD_CLASS } from "./desk-kpi";
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
      <SheetContent className="w-full overflow-y-auto border-l border-border/70 bg-background sm:max-w-lg">
        <SheetHeader className="space-y-2 border-b border-border/60 pb-4">
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-primary">
            Account detail
          </p>
          <SheetTitle>{user.email}</SheetTitle>
          <SheetDescription>
            {user.firstName} {user.lastName}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 flex flex-col gap-6">
          <DeskMetricGrid className="grid-cols-1 sm:grid-cols-2">
            <DeskMetricCard
              label="Account status"
              value={
                <Badge variant={user.isActive ? "success" : "warning"}>
                  {user.isActive ? "Active" : "Suspended"}
                </Badge>
              }
              hint={`Created ${formatDate(user.createdAt)}`}
              className={DESK_KPI_CARD_CLASS}
            />
            <DeskMetricCard
              label="Verification and MFA"
              value={
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={user.isVerified ? "success" : "outline"}>
                    {user.isVerified ? "Verified" : "Unverified"}
                  </Badge>
                  <Badge variant={user.mfaEnabled ? "success" : "outline"}>
                    {user.mfaEnabled ? "MFA enabled" : "MFA off"}
                  </Badge>
                </div>
              }
              hint="Security posture for this account"
              className={DESK_KPI_CARD_CLASS}
            />
          </DeskMetricGrid>

          <section className="rounded-xl border border-border/70 bg-card p-4 shadow-sm">
            <SectionHeader>
              <SectionHeaderContent>
                <SectionHeaderTitle>Account details</SectionHeaderTitle>
                <SectionHeaderDescription>
                  Read-only identity and role posture for this user. Mutating role assignment stays
                  disabled until ADR21 controls land.
                </SectionHeaderDescription>
              </SectionHeaderContent>
            </SectionHeader>
            <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-muted-foreground">Full name</dt>
                <dd>
                  {user.firstName} {user.lastName}
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
                  Role assignment is unavailable in Wave 2 until ADR21 `P3` controls are
                  implemented.
                </p>
              </div>
            </dl>
          </section>

          <div>
            <SectionHeader className="mb-3">
              <SectionHeaderContent>
                <SectionHeaderTitle>Recent admin actions on this user</SectionHeaderTitle>
                <SectionHeaderDescription>
                  Page-scoped audit entries resolved from the current audit feed.
                </SectionHeaderDescription>
              </SectionHeaderContent>
            </SectionHeader>
            <AuditLogTable targetId={user.id} />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function formatDate(value: string) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}
