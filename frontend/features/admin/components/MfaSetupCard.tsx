"use client";

import { useState } from "react";
import { Check, Copy, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
 */
export function MfaSetupCard() {
  const { data: status, isLoading } = useMfaStatus();
  const enroll = useEnrollMfa();
  const confirmEnrollment = useConfirmMfaEnrollment();
  const disableMfa = useDisableMfa();

  const [code, setCode] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  async function handleDisable() {
    setError(null);
    const confirmed = window.confirm("Disable two-factor authentication for your account?");
    if (!confirmed) return;
    const disableCode = window.prompt("Enter your current 6-digit MFA code to disable 2FA:", "");
    if (!disableCode?.trim()) return;

    try {
      await disableMfa.mutateAsync(disableCode.trim());
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
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <ShieldCheck className="size-5" />
          Two-factor authentication
        </CardTitle>
        <CardDescription>
          Protect your account with a time-based one-time code (TOTP) from an authenticator app.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {status?.mfaEnabled ? (
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div>
              <p className="text-sm font-medium">2FA is enabled</p>
              <p className="text-sm text-muted-foreground">
                Enrolled {status.mfaEnrolledAt ? formatDate(status.mfaEnrolledAt) : ""}
              </p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <Button
                variant="destructive"
                onClick={() => void handleDisable()}
                disabled={disableMfa.isPending}
              >
                {disableMfa.isPending ? "Disabling…" : "Disable 2FA"}
              </Button>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
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
                Enter this secret (or scan the provisioning URI below) into your authenticator app.
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
  );
}

function formatDate(value: string) {
  if (!value) return "";
  return `on ${value.replace("T", " ").slice(0, 19)}`;
}
