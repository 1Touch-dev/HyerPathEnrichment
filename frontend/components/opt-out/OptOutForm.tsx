"use client";

import { useState } from "react";
import { submitDsar, submitOptOut } from "@/src/lib/api-client";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import { DsarType } from "@/src/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type RequestMode = "opt_out" | DsarType;

const MODE_LABELS: Record<RequestMode, string> = {
  opt_out: "Opt out",
  access: "Data access (DSAR)",
  deletion: "Data deletion (DSAR)",
};

export function OptOutForm() {
  const [mode, setMode] = useState<RequestMode>("opt_out");
  const [identifier, setIdentifier] = useState("");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const trimmed = identifier.trim();
      if (mode === "opt_out") {
        await submitOptOut({ identifier: trimmed, reason: reason.trim() || undefined });
      } else {
        const response = await submitDsar({
          identifier: trimmed,
          requestType: mode,
          notes: reason.trim() || undefined,
        });
        setSummary(response.data.summary);
      }
      setSubmitted(true);
    } catch (submitError) {
      setError(formatApiErrorMessage(submitError));
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <Card className="border-success/30" data-testid="opt-out-success">
        <CardHeader>
          <p className="text-xs font-semibold uppercase tracking-widest text-success">Accepted</p>
          <CardTitle>Request accepted</CardTitle>
          <CardDescription>We process data subject requests within 30 days.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {mode === "opt_out" ? (
            <p className="text-sm text-muted-foreground">
              Your identifier has been suppressed and stored enrichment data has been purged. Future
              requests return an empty dossier.
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Your {MODE_LABELS[mode].toLowerCase()} request was processed. Summary below contains
              counts only — no dossier PII.
            </p>
          )}
          {summary ? (
            <pre className="overflow-x-auto rounded-md border border-border bg-muted p-3 font-mono text-xs">
              {JSON.stringify(summary, null, 2)}
            </pre>
          ) : null}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border" data-testid="opt-out-form">
      <CardHeader>
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">
          Data subject request
        </p>
        <CardTitle>Compliance requests</CardTitle>
        <CardDescription>
          Opt out of enrichment, request a copy of stored metadata, or request deletion
          (LGPD/GDPR/CCPA).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex flex-wrap gap-2">
          {(Object.keys(MODE_LABELS) as RequestMode[]).map((key) => (
            <Button
              key={key}
              type="button"
              size="sm"
              variant={mode === key ? "default" : "outline"}
              onClick={() => setMode(key)}
            >
              {MODE_LABELS[key]}
            </Button>
          ))}
        </div>

        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="identifier">Identifier</Label>
            <Input
              id="identifier"
              required
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="email, LinkedIn URL, or username"
              className="font-mono text-sm"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="reason">
              {mode === "opt_out" ? "Reason (optional)" : "Notes (optional)"}
            </Label>
            <Textarea
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Optional context for your request"
            />
          </div>
          <Button type="submit" disabled={loading || !identifier.trim()}>
            {loading ? "Submitting…" : `Submit ${MODE_LABELS[mode].toLowerCase()}`}
          </Button>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </form>
      </CardContent>
    </Card>
  );
}
