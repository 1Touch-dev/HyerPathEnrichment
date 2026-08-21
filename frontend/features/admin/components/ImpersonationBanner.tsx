"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useEndImpersonation, useImpersonationStatus } from "../hooks/useImpersonation";

/**
 * Always mounted inside AppShell, renders nothing when not impersonating.
 * Directly implements Zendesk's warning (§11.5): the *acting* identity must
 * always be visible, not just logged in the audit trail.
 */
export function ImpersonationBanner() {
  const { data: status } = useImpersonationStatus();
  const endImpersonation = useEndImpersonation();
  const [error, setError] = useState<string | null>(null);

  if (!status?.isImpersonating) return null;

  async function handleExit() {
    setError(null);
    try {
      await endImpersonation.mutateAsync();
      window.location.assign("/app/admin/users");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to exit impersonation.");
    }
  }

  return (
    <div className="flex items-center justify-between gap-4 bg-destructive px-4 py-2 text-sm text-destructive-foreground sm:px-6">
      <div className="flex items-center gap-2">
        <AlertTriangle className="size-4 shrink-0" />
        <span>
          You are viewing as <strong>{status.targetUserId}</strong> — admin: {status.adminEmail}
        </span>
        {error ? <span className="ml-2 opacity-90">({error})</span> : null}
      </div>
      <Button
        variant="outline"
        size="sm"
        className="border-destructive-foreground/40 bg-transparent text-destructive-foreground hover:bg-destructive-foreground/10"
        onClick={() => void handleExit()}
        disabled={endImpersonation.isPending}
      >
        {endImpersonation.isPending ? "Exiting…" : "Exit impersonation"}
      </Button>
    </div>
  );
}
