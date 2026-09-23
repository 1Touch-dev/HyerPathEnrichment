"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { DeskMetricCard, DeskMetricGrid, DeskPage } from "@/components/desk/desk-shell";
import { EmptyState } from "@/components/console/EmptyState";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
  SectionHeader,
  SectionHeaderActions,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderTitle,
} from "@/components/ui/section-header";

const DESK_KPI_CARD_CLASS = "border-border/70 bg-card";

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
  const acceptedInvites = invites.filter((invite) => Boolean(invite.acceptedAt)).length;

  const createInviteMutation = useMutation({
    mutationFn: createStaffInvite,
    onSuccess: (invite) => {
      setInvites((prev) => [invite, ...prev]);
      setCreateDialogOpen(false);
    },
  });

  return (
    <DeskPage
      eyebrow="Desk administration"
      title="Staff invites"
      description="Create staff registration invites with the same session-only roster behavior until a historical list endpoint exists."
      actions={<Button onClick={() => setCreateDialogOpen(true)}>Invite staff member</Button>}
    >
      <Alert variant="info">
        <AlertTitle>Session-only roster</AlertTitle>
        <AlertDescription>
          No historical list endpoint exists yet. This page only shows invites created during the
          current session.
        </AlertDescription>
      </Alert>

      <DeskMetricGrid className="xl:grid-cols-3">
        <DeskMetricCard
          label="Invites this session"
          value={invites.length}
          hint="Created in this tab"
          className={DESK_KPI_CARD_CLASS}
        />
        <DeskMetricCard
          label="Accepted in this session"
          value={acceptedInvites}
          hint={`${invites.length - acceptedInvites} pending invite(s)`}
          className={DESK_KPI_CARD_CLASS}
        />
        <DeskMetricCard
          label="Role assignment"
          value="Preset on create"
          hint="Recipients register with the assigned staff role"
          className={DESK_KPI_CARD_CLASS}
        />
      </DeskMetricGrid>

      {!invites.length ? (
        <EmptyState
          title="No invites in this session"
          description="This list is session-only and is not loaded from the server. Invites sent earlier or in another tab will not appear here."
        />
      ) : (
        <div className="flex flex-col gap-4">
          <SectionHeader>
            <SectionHeaderContent>
              <SectionHeaderTitle>Invite activity</SectionHeaderTitle>
              <SectionHeaderDescription>
                Track the invites created during this session and whether they have been accepted.
              </SectionHeaderDescription>
            </SectionHeaderContent>
            <SectionHeaderActions>
              <Badge variant="outline">Session-local only</Badge>
            </SectionHeaderActions>
          </SectionHeader>
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
        </div>
      )}

      <CreateStaffInviteDialog
        open={createDialogOpen}
        isPending={createInviteMutation.isPending}
        onOpenChange={setCreateDialogOpen}
        onConfirm={(payload) => createInviteMutation.mutate(payload)}
      />
    </DeskPage>
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
      <DialogContent className="gap-0 overflow-hidden border-border/70 p-0 sm:max-w-md">
        <div className="border-b border-border/60 bg-primary-soft/50 px-6 py-5">
          <DialogHeader className="space-y-2 text-left">
            <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-primary">
              Staff access
            </p>
            <DialogTitle>Invite staff member</DialogTitle>
            <DialogDescription>
              Sends an invite the recipient can use to register with a staff role already assigned.
            </DialogDescription>
          </DialogHeader>
        </div>

        <div className="space-y-4 bg-card px-6 py-5">
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
        </div>
      </DialogContent>
    </Dialog>
  );
}
