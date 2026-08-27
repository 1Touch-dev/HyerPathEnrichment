"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
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

type StaffInvite = {
  id: string;
  email: string;
  roleName: string;
  expiresAt: string;
  acceptedAt: string | null;
};

type BackendStaffInviteResponse = {
  id: string;
  email: string;
  role_name: string;
  expires_at: string;
  accepted_at: string | null;
};

async function createStaffInvite(body: { email: string; role_name: string }): Promise<StaffInvite> {
  const res = await fetch("/api/admin/staff-invites", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed to create staff invite: ${res.status}`);
  const json = await res.json();
  const raw = json.data as BackendStaffInviteResponse;
  return {
    id: raw.id,
    email: raw.email,
    roleName: raw.role_name,
    expiresAt: raw.expires_at,
    acceptedAt: raw.accepted_at,
  };
}

/**
 * No "list all invites" endpoint exists on the backend yet (confirmed:
 * staff_invites/router.py only exposes POST /api/staff-invites and the public
 * GET /api/staff-invites/{token}) — this page's "list" is therefore the set of
 * invites created during this session, prepended to on each successful
 * creation, rather than a query re-fetched from a nonexistent list endpoint.
 */
export default function AdminStaffInvitesPage() {
  const [invites, setInvites] = useState<StaffInvite[]>([]);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  const createInviteMutation = useMutation({
    mutationFn: createStaffInvite,
    onSuccess: (invite) => {
      setInvites((prev) => [invite, ...prev]);
      setCreateDialogOpen(false);
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Staff invites</h1>
        <Button onClick={() => setCreateDialogOpen(true)}>Invite staff member</Button>
      </div>
      {!invites.length ? (
        <EmptyState
          title="No invites sent yet"
          description="Invites you create this session appear here."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {invites.map((invite) => (
            <Card key={invite.id}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  {invite.email}
                  <Badge variant={invite.acceptedAt ? "secondary" : "outline"}>
                    {invite.acceptedAt ? "Accepted" : "Pending"}
                  </Badge>
                </CardTitle>
                <p className="text-sm text-muted-foreground">Role: {invite.roleName}</p>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Expires {new Date(invite.expiresAt).toLocaleString()}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CreateStaffInviteDialog
        open={createDialogOpen}
        isPending={createInviteMutation.isPending}
        onOpenChange={setCreateDialogOpen}
        onConfirm={(payload) => createInviteMutation.mutate(payload)}
      />
    </div>
  );
}

interface CreateStaffInviteDialogProps {
  open: boolean;
  isPending?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (payload: { email: string; role_name: string }) => void;
}

function CreateStaffInviteDialog({
  open,
  isPending = false,
  onOpenChange,
  onConfirm,
}: CreateStaffInviteDialogProps) {
  const [email, setEmail] = useState("");
  const [roleName, setRoleName] = useState("recruiter");

  function handleOpenChange(next: boolean) {
    if (!next) {
      setEmail("");
      setRoleName("recruiter");
    }
    onOpenChange(next);
  }

  function handleConfirm() {
    onConfirm({ email: email.trim(), role_name: roleName.trim() || "recruiter" });
  }

  const isEmailInvalid = email.trim().length === 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite staff member</DialogTitle>
          <DialogDescription>
            Sends an invite the recipient can use to register with a staff role already assigned.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="invite-email">Email</Label>
          <Input
            id="invite-email"
            type="email"
            placeholder="teammate@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="invite-role">Role name</Label>
          <Input
            id="invite-role"
            placeholder="recruiter"
            value={roleName}
            onChange={(e) => setRoleName(e.target.value)}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={isPending || isEmailInvalid}>
            {isPending ? "Sending..." : "Send invite"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
