"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  attachPermission,
  createRole,
  detachPermission,
  fetchRoles,
} from "@/features/admin/api/client";
import { adminKeys } from "@/features/admin/api/keys";
import type { AdminPermission, AdminRoleWithPermissions } from "@/src/lib/types";

/**
 * Read-only role/permission matrix. `fetchRoles()` is typed `Promise<AdminRole[]>`
 * (§12.1/12.2's verbatim client), but the `/api/admin/roles` BFF route actually
 * returns `AdminRoleWithPermissions[]` (it maps through `mapBackendRoleWithPermissions`)
 * — this page reads the real richer shape returned at runtime rather than adding
 * a second, parallel roles-fetching function just to get a wider return type.
 */
export default function AdminRolesPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: adminKeys.roles(), queryFn: fetchRoles });
  const roles = useMemo(() => (data ?? []) as unknown as AdminRoleWithPermissions[], [data]);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  // No dedicated "list all permissions" endpoint exists yet (confirmed by reading
  // roles_router.py — only GET/POST "" and POST/DELETE ".../permissions" exist).
  // The union of every already-fetched role's permissions is therefore the
  // simplest correct source for the attach-permission `<Select>`'s option list:
  // it's always in sync with `fetchRoles()`'s own cache/invalidation, requires no
  // new endpoint, and already contains every permission row that exists (every
  // permission was seeded onto at least one role by the admin-module migrations).
  const allPermissions = useMemo(() => {
    const byId = new Map<string, AdminPermission>();
    for (const role of roles) {
      for (const permission of role.permissions) {
        byId.set(permission.id, permission);
      }
    }
    return Array.from(byId.values()).sort((a, b) =>
      `${a.resource}:${a.action}`.localeCompare(`${b.resource}:${b.action}`),
    );
  }, [roles]);

  const createRoleMutation = useMutation({
    mutationFn: createRole,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.roles() });
      setCreateDialogOpen(false);
    },
  });

  const attachPermissionMutation = useMutation({
    mutationFn: ({ roleId, permissionId }: { roleId: string; permissionId: string }) =>
      attachPermission(roleId, permissionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.roles() }),
  });

  const detachPermissionMutation = useMutation({
    mutationFn: ({ roleId, permissionId }: { roleId: string; permissionId: string }) =>
      detachPermission(roleId, permissionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.roles() }),
  });

  if (isLoading && !data) {
    return <p className="text-sm text-muted-foreground">Loading roles…</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Roles</h1>
        <Button onClick={() => setCreateDialogOpen(true)}>Create role</Button>
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
                    <Badge key={permission.id} variant="secondary" className="gap-1">
                      {permission.resource}:{permission.action}
                      {!role.isSystem ? (
                        <button
                          type="button"
                          aria-label={`Remove ${permission.resource}:${permission.action} from ${role.name}`}
                          className="rounded-full hover:text-destructive focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                          disabled={detachPermissionMutation.isPending}
                          onClick={() =>
                            detachPermissionMutation.mutate({
                              roleId: role.id,
                              permissionId: permission.id,
                            })
                          }
                        >
                          <X className="h-3 w-3" />
                        </button>
                      ) : null}
                    </Badge>
                  ))}
                </div>
                {!role.isSystem ? (
                  <AttachPermissionControl
                    role={role}
                    availablePermissions={allPermissions}
                    isPending={attachPermissionMutation.isPending}
                    onAttach={(permissionId) =>
                      attachPermissionMutation.mutate({ roleId: role.id, permissionId })
                    }
                  />
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CreateRoleDialog
        open={createDialogOpen}
        isPending={createRoleMutation.isPending}
        onOpenChange={setCreateDialogOpen}
        onConfirm={(payload) => createRoleMutation.mutate(payload)}
      />
    </div>
  );
}

interface AttachPermissionControlProps {
  role: AdminRoleWithPermissions;
  availablePermissions: AdminPermission[];
  isPending: boolean;
  onAttach: (permissionId: string) => void;
}

function AttachPermissionControl({
  role,
  availablePermissions,
  isPending,
  onAttach,
}: AttachPermissionControlProps) {
  const [selectedPermissionId, setSelectedPermissionId] = useState<string>("");
  const attachedIds = new Set(role.permissions.map((permission) => permission.id));
  const options = availablePermissions.filter((permission) => !attachedIds.has(permission.id));

  function handleAdd() {
    if (!selectedPermissionId) return;
    onAttach(selectedPermissionId);
    setSelectedPermissionId("");
  }

  return (
    <div className="flex items-center gap-2">
      <Select value={selectedPermissionId} onValueChange={setSelectedPermissionId}>
        <SelectTrigger
          aria-label={`Attach permission to ${role.name}`}
          className="h-8 w-full text-xs"
        >
          <SelectValue placeholder="Attach permission…" />
        </SelectTrigger>
        <SelectContent>
          {options.map((permission) => (
            <SelectItem key={permission.id} value={permission.id}>
              {permission.resource}:{permission.action}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button
        size="sm"
        variant="outline"
        disabled={!selectedPermissionId || isPending}
        onClick={handleAdd}
      >
        Add
      </Button>
    </div>
  );
}

interface CreateRoleDialogProps {
  open: boolean;
  isPending?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (payload: { name: string; description?: string | null }) => void;
}

function CreateRoleDialog({
  open,
  isPending = false,
  onOpenChange,
  onConfirm,
}: CreateRoleDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function handleOpenChange(next: boolean) {
    if (!next) {
      setName("");
      setDescription("");
    }
    onOpenChange(next);
  }

  function handleConfirm() {
    onConfirm({ name: name.trim(), description: description.trim() || undefined });
  }

  const isNameInvalid = name.trim().length === 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create role</DialogTitle>
          <DialogDescription>
            New roles start with no permissions attached — add them from each role&apos;s card after
            creating it.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="create-role-name">Name</Label>
          <Input
            id="create-role-name"
            placeholder="e.g. content_moderator"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="create-role-description">Description</Label>
          <Input
            id="create-role-description"
            placeholder="Optional"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={isPending || isNameInvalid}>
            {isPending ? "Creating..." : "Create role"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
