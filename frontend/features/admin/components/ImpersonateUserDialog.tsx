"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/providers/auth-provider";
import type { AdminUser } from "@/src/lib/types";
import { useStartImpersonation } from "../hooks/useImpersonation";

const MIN_REASON_LENGTH = 3;

type ImpersonateUserDialogProps = {
  user: AdminUser;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/**
 * Launched from UsersTable's "Log in as" action. Only asks for an MFA code
 * when the *acting admin's own* mfaEnabled is true, mirroring the backend's
 * conditional enforcement (§8.14) — the target user's MFA status is unrelated.
 */
export function ImpersonateUserDialog({ user, open, onOpenChange }: ImpersonateUserDialogProps) {
  const { user: currentUser } = useAuth();
  const startImpersonation = useStartImpersonation();
  const [reason, setReason] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const requiresMfaCode = !!currentUser?.mfa_enabled;
  const isReasonValid = reason.trim().length >= MIN_REASON_LENGTH;
  const canSubmit = isReasonValid && (!requiresMfaCode || mfaCode.trim().length > 0);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    try {
      await startImpersonation.mutateAsync({
        userId: user.id,
        reason: reason.trim(),
        mfaCode: requiresMfaCode ? mfaCode.trim() : undefined,
      });
      // Full page navigation (not client-side routing) so the new
      // impersonation cookie takes effect on the very next request.
      window.location.assign("/app/matches");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start impersonation.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Log in as {user.email}</DialogTitle>
          <DialogDescription>
            You will act as this user until you end the session. This is logged.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="impersonation-reason">Reason</Label>
            <Textarea
              id="impersonation-reason"
              placeholder="e.g. Investigating a support ticket about missing matches"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
              minLength={MIN_REASON_LENGTH}
            />
          </div>
          {requiresMfaCode ? (
            <div>
              <Label htmlFor="impersonation-mfa-code">Your 2FA code</Label>
              <Input
                id="impersonation-mfa-code"
                inputMode="numeric"
                placeholder="123456"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                required
              />
            </div>
          ) : null}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit || startImpersonation.isPending}>
              {startImpersonation.isPending ? "Starting…" : "Log in as user"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
