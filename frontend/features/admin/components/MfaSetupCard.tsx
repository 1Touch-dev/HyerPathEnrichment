"use client";

import { useState } from "react";
import { Check, Copy, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { copyToClipboard } from "@/src/lib/utils";
import {
  useConfirmMfaEnrollment,
  useDisableMfa,
  useEnrollMfa,
  useMfaStatus,
} from "../hooks/useMfaSetup";

/**
 * Self-service — any verified user, not just admins, per Decision 5. Shows
 * the enrollment secret/provisioning URI as copyable text: this repo has no
 * QR-code rendering library yet, so the "copyable secret" fallback mentioned
 * in §12.4 is used directly rather than adding a new dependency for a QR
 * image that a password-manager-based TOTP flow doesn't strictly need.
 *
 * Disable flow: Figma §14 prefers a Dialog over `window.confirm` + `prompt`.
 * Semantics stay the same — user must confirm intent and supply a current
 * 6-digit code before `useDisableMfa` runs; cancel / empty code aborts.
 */
export function MfaSetupCard() {
  const { data: status, isLoading } = useMfaStatus();
  const enroll = useEnrollMfa();
  const confirmEnrollment = useConfirmMfaEnrollment();
  const disableMfa = useDisableMfa();

  const [code, setCode] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [disableOpen, setDisableOpen] = useState(false);
  const [disableCode, setDisableCode] = useState("");

  async function handleStartEnroll() {
    setError(null);
    try {
      await enroll.mutateAsync();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start MFA enrollment.");
    }
  }

  async function handleCopySecret() {
    if (!enroll.data?.secret) return;
    await copyToClipboard(enroll.data.secret);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function handleConfirm(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await confirmEnrollment.mutateAsync(code);
      setCode("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid or expired code.");
    }
  }

  function openDisableDialog() {
    setError(null);
    setDisableCode("");
    setDisableOpen(true);
  }

  function handleDisableOpenChange(open: boolean) {
    if (!open) {
      setDisableCode("");
    }
    setDisableOpen(open);
  }

  async function handleDisableSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = disableCode.trim();
    if (!trimmed) return;

    setError(null);
    try {
      await disableMfa.mutateAsync(trimmed);
      setDisableOpen(false);
      setDisableCode("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to disable MFA.");
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-10">
          <p className="text-sm text-muted-foreground">Loading MFA status…</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card className="border-border/70">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <ShieldCheck className="size-5 text-primary" />
            Two-factor authentication
          </CardTitle>
          <CardDescription>
            Protect your account with a time-based one-time code (TOTP) from an authenticator app.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {status?.mfaEnabled ? (
            <div className="flex flex-col gap-4 rounded-xl border border-border/70 bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium">2FA is enabled</p>
                <p className="text-sm text-muted-foreground">
                  Enrolled {status.mfaEnrolledAt ? formatDate(status.mfaEnrolledAt) : ""}
                </p>
              </div>
              <div className="flex flex-col items-stretch gap-2 sm:items-end">
                <Button
                  variant="destructive"
                  onClick={openDisableDialog}
                  disabled={disableMfa.isPending}
                >
                  {disableMfa.isPending ? "Disabling…" : "Disable 2FA"}
                </Button>
                {error && !disableOpen ? <p className="text-sm text-destructive">{error}</p> : null}
              </div>
            </div>
          ) : enroll.data ? (
            <form onSubmit={handleConfirm} className="space-y-4">
              <div>
                <Label>Setup secret</Label>
                <div className="flex items-center gap-2">
                  <Input readOnly value={enroll.data.secret} className="font-mono" />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => void handleCopySecret()}
                  >
                    {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                  </Button>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  Enter this secret (or scan the provisioning URI below) into your authenticator
                  app.
                </p>
                <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                  {enroll.data.provisioningUri}
                </p>
              </div>
              <div>
                <Label htmlFor="mfa-confirm-code">6-digit code</Label>
                <Input
                  id="mfa-confirm-code"
                  inputMode="numeric"
                  placeholder="123456"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                />
              </div>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              <Button type="submit" disabled={confirmEnrollment.isPending}>
                {confirmEnrollment.isPending ? "Confirming…" : "Confirm and enable 2FA"}
              </Button>
            </form>
          ) : (
            <div>
              {error ? <p className="mb-2 text-sm text-destructive">{error}</p> : null}
              <Button onClick={() => void handleStartEnroll()} disabled={enroll.isPending}>
                {enroll.isPending ? "Starting…" : "Enable 2FA"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={disableOpen} onOpenChange={handleDisableOpenChange}>
        <DialogContent className="gap-0 overflow-hidden border-border/70 p-0 sm:max-w-md">
          <div className="border-b border-border/60 bg-primary-soft/50 px-6 py-5">
            <DialogHeader className="space-y-2 text-left">
              <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-primary">
                Security
              </p>
              <DialogTitle>Disable two-factor authentication?</DialogTitle>
              <DialogDescription>
                This removes TOTP protection from your account. Enter your current 6-digit code to
                confirm.
              </DialogDescription>
            </DialogHeader>
          </div>
          <form
            onSubmit={(e) => void handleDisableSubmit(e)}
            className="space-y-4 bg-card px-6 py-5"
          >
            <div className="space-y-2">
              <Label htmlFor="mfa-disable-code">6-digit MFA code</Label>
              <Input
                id="mfa-disable-code"
                inputMode="numeric"
                placeholder="123456"
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value)}
                autoComplete="one-time-code"
                required
              />
            </div>
            {error && disableOpen ? <p className="text-sm text-destructive">{error}</p> : null}
            <DialogFooter className="gap-2 sm:gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleDisableOpenChange(false)}
                disabled={disableMfa.isPending}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="destructive"
                disabled={disableMfa.isPending || !disableCode.trim()}
              >
                {disableMfa.isPending ? "Disabling…" : "Disable 2FA"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function formatDate(value: string) {
  if (!value) return "";
  return `on ${value.replace("T", " ").slice(0, 19)}`;
}
