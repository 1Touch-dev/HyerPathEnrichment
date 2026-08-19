"use client";

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
  const { data, isLoading } = useQuery({ queryKey: adminKeys.roles(), queryFn: fetchRoles });
  const roles = (data ?? []) as unknown as AdminRoleWithPermissions[];

  if (isLoading && !data) {
    return <p className="text-sm text-muted-foreground">Loading roles…</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Roles</h1>
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
              <CardContent>
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
