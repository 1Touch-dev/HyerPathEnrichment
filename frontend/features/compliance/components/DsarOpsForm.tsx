"use client";

import { useState } from "react";
import { submitDsar } from "@/src/lib/api-client";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import { DsarType } from "@/src/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const DSAR_LABELS: Record<DsarType, string> = {
  access: "Data access (DSAR)",
  deletion: "Data deletion (DSAR)",
};

export function DsarOpsForm() {
  const [requestType, setRequestType] = useState<DsarType>("access");
  const [identifier, setIdentifier] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    setSummary(null);

    try {
      const response = await submitDsar({
        identifier: identifier.trim(),
        requestType,
        notes: notes.trim() || undefined,
      });
      setSummary(response.data.summary);
    } catch (submitError) {
      setError(formatApiErrorMessage(submitError));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>DSAR operations</CardTitle>
        <CardDescription>
          Internal access and deletion requests. Public opt-out is at /opt-out.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex flex-wrap gap-2">
          {(Object.keys(DSAR_LABELS) as DsarType[]).map((type) => (
            <Button
              key={type}
              type="button"
              size="sm"
              variant={requestType === type ? "default" : "outline"}
              onClick={() => setRequestType(type)}
            >
              {DSAR_LABELS[type]}
            </Button>
          ))}
        </div>

        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="dsar-identifier">Identifier</Label>
            <Input
              id="dsar-identifier"
              required
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="email, LinkedIn URL, or username"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="dsar-notes">Notes (optional)</Label>
            <Textarea
              id="dsar-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Internal ops notes"
            />
          </div>
          <Button type="submit" disabled={loading || !identifier.trim()}>
            {loading ? "Submitting…" : `Submit ${DSAR_LABELS[requestType].toLowerCase()}`}
          </Button>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {summary ? (
            <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs">
              {JSON.stringify(summary, null, 2)}
            </pre>
          ) : null}
        </form>
      </CardContent>
    </Card>
  );
}
