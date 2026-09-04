"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchRoles } from "@/features/admin/api/client";
import { adminKeys } from "@/features/admin/api/keys";
import type { AdminRoleWithPermissions } from "@/src/lib/types";

/**
 * Read-only role/permission matrix. `fetchRoles()` is typed `Promise<AdminRole[]>`
 * (§12.1/12.2's verbatim client), but the `/api/admin/roles` BFF route actually
 * returns `AdminRoleWithPermissions[]` (it maps through `mapBackendRoleWithPermissions`)
 * — this page reads the real richer shape returned at runtime rather than adding
 * a second, parallel roles-fetching function just to get a wider return type.
 */
export default function AdminRolesPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: adminKeys.roles(),
    queryFn: fetchRoles,
  });
  const roles = useMemo(() => (data ?? []) as unknown as AdminRoleWithPermissions[], [data]);

  if (isLoading && !data) {
    return (
      <p role="status" className="text-sm text-muted-foreground">
        Loading roles…
      </p>
    );
  }

  if (isError) {
    const detail = error instanceof Error ? error.message : null;
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Roles</h1>
        <div
          role="alert"
          aria-label="Could not load roles"
          aria-description="Access failed or permissions are missing for the roles API."
        >
          <EmptyState
            title="Could not load roles"
            description={
              detail
                ? `Access failed or permissions are missing. (${detail})`
                : "Access failed or permissions are missing. You may not have permission to view roles."
            }
          />
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Roles</h1>
        <p className="text-sm text-muted-foreground">
          Role and permission mutations are temporarily unavailable until ADR21 typed confirmation
          and step-up controls are implemented.
        </p>
      </div>
      {!roles.length ? (
        <EmptyState title="No roles configured" description="Roles are seeded via migration." />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {roles.map((role) => (
            <Card key={role.id}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  {role.name}
                  {role.isSystem ? <Badge variant="outline">System</Badge> : null}
                </CardTitle>
                {role.description ? (
                  <p className="text-sm text-muted-foreground">{role.description}</p>
                ) : null}
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="flex flex-wrap gap-1.5">
                  {role.permissions.map((permission) => (
                    <Badge key={permission.id} variant="secondary">
                      {permission.resource}:{permission.action}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
