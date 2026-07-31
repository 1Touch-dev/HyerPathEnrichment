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
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

const DSAR_LABELS: Record<DsarType, string> = {
  access: "Data access (DSAR)",
  deletion: "Data deletion (DSAR)",
};

interface EnrichedData {
  photo?: {
    source: string;
    asset_url: string;
    captured_at: string;
    confidence: number;
  };
  handles?: Array<{
    platform: string;
    username: string;
    profile_url: string;
    confidence: number;
  }>;
  emails?: string[];
  verified_emails?: Array<{
    value: string;
    status: string;
    confidence: number;
    source: string;
  }>;
  github?: Record<string, unknown>;
  coworkers?: string[];
  jobs?: Array<{
    title: string;
    company: string;
    location: string;
    remote: boolean;
    source: string;
  }>;
  business?: {
    name: string;
    address: string;
    website: string;
    rating: number;
    phone: string;
  };
  sources?: string[];
  confidence?: Array<{
    label: string;
    score: number;
    evidence: string[];
  }>;
}

interface DsarSummary {
  job_count: number;
  photo_cached?: boolean;
  first_job_at?: string;
  last_job_at?: string;
  identifier_provided?: string;
  enriched_data?: EnrichedData | null;
  suppressed?: boolean;
  jobs_cleared?: number;
  photos_deleted?: number;
  r2_objects_deleted?: number;
}

function MetadataSummary({ summary }: { summary: DsarSummary }) {
  return (
    <div className="rounded-md bg-muted p-4">
      <h3 className="mb-3 font-semibold">Summary</h3>
      <div className="grid gap-2 text-sm">
        {summary.identifier_provided && (
          <div>
            <span className="text-muted-foreground">Identifier:</span>{" "}
            <span className="font-mono">{summary.identifier_provided}</span>
          </div>
        )}
        <div>
          <span className="text-muted-foreground">Jobs found:</span> {summary.job_count}
        </div>
        {summary.first_job_at && (
          <div>
            <span className="text-muted-foreground">First enrichment:</span>{" "}
            {new Date(summary.first_job_at).toLocaleString()}
          </div>
        )}
        {summary.last_job_at && (
          <div>
            <span className="text-muted-foreground">Last enrichment:</span>{" "}
            {new Date(summary.last_job_at).toLocaleString()}
          </div>
        )}
        {summary.photo_cached !== undefined && (
          <div>
            <span className="text-muted-foreground">Photo cached:</span>{" "}
            {summary.photo_cached ? "Yes" : "No"}
          </div>
        )}
      </div>
    </div>
  );
}

function PhotoSection({ photo }: { photo: NonNullable<EnrichedData["photo"]> }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Photo</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {photo.asset_url && (
            <img
              src={photo.asset_url}
              alt="Profile"
              className="h-32 w-32 rounded-lg object-cover"
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
            />
          )}
          <div className="grid gap-2 text-sm">
            <div>
              <span className="text-muted-foreground">Source:</span> {photo.source}
            </div>
            <div>
              <span className="text-muted-foreground">Confidence:</span>{" "}
              {(photo.confidence * 100).toFixed(0)}%
            </div>
            <div>
              <span className="text-muted-foreground">Captured:</span>{" "}
              {new Date(photo.captured_at).toLocaleString()}
            </div>
            <div className="break-all">
              <span className="text-muted-foreground">URL:</span>{" "}
              <a
                href={photo.asset_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                {photo.asset_url}
              </a>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function EmailsSection({
  emails,
  verifiedEmails,
}: {
  emails?: string[];
  verifiedEmails?: EnrichedData["verified_emails"];
}) {
  const hasEmails = (emails && emails.length > 0) || (verifiedEmails && verifiedEmails.length > 0);
  if (!hasEmails) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Emails</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {emails && emails.length > 0 && (
            <div>
              <div className="mb-2 text-sm font-medium">Discovered Emails</div>
              <div className="flex flex-wrap gap-2">
                {emails.map((email, idx) => (
                  <Badge key={idx} variant="secondary">
                    {email}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {verifiedEmails && verifiedEmails.length > 0 && (
            <div>
              <div className="mb-2 text-sm font-medium">Verified Emails</div>
              <div className="space-y-2">
                {verifiedEmails.map((email, idx) => (
                  <div key={idx} className="flex items-center gap-2 text-sm">
                    <Badge variant={email.status === "valid" ? "default" : "secondary"}>
                      {email.value}
                    </Badge>
                    <span className="text-muted-foreground">
                      {email.status} ({(email.confidence * 100).toFixed(0)}%)
                    </span>
                    <span className="text-xs text-muted-foreground">via {email.source}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function HandlesSection({ handles }: { handles: NonNullable<EnrichedData["handles"]> }) {
  if (handles.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Social Handles</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {handles.map((handle, idx) => (
            <div key={idx} className="flex items-center justify-between rounded-md border p-3">
              <div className="flex-1">
                <div className="font-medium">{handle.platform}</div>
                <a
                  href={handle.profile_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline"
                >
                  @{handle.username}
                </a>
              </div>
              <Badge variant="outline">{(handle.confidence * 100).toFixed(0)}%</Badge>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function BusinessSection({ business }: { business: NonNullable<EnrichedData["business"]> }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Business Profile</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 text-sm">
          <div>
            <span className="font-medium">{business.name}</span>
          </div>
          <div className="text-muted-foreground">{business.address}</div>
          {business.website && (
            <div>
              <a
                href={business.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                {business.website}
              </a>
            </div>
          )}
          {business.phone && <div>Phone: {business.phone}</div>}
          {business.rating > 0 && <div>Rating: {business.rating.toFixed(1)} / 5.0</div>}
        </div>
      </CardContent>
    </Card>
  );
}

function DeletionSummary({ summary }: { summary: DsarSummary }) {
  return (
    <div className="rounded-md bg-muted p-4">
      <h3 className="mb-3 font-semibold">Deletion Summary</h3>
      <div className="grid gap-2 text-sm">
        <div>
          <span className="text-muted-foreground">Status:</span>{" "}
          <Badge variant={summary.suppressed ? "default" : "secondary"}>
            {summary.suppressed ? "Suppressed" : "Pending"}
          </Badge>
        </div>
        <div>
          <span className="text-muted-foreground">Jobs cleared:</span> {summary.jobs_cleared ?? 0}
        </div>
        <div>
          <span className="text-muted-foreground">Photos deleted:</span>{" "}
          {summary.photos_deleted ?? 0}
        </div>
        <div>
          <span className="text-muted-foreground">R2 objects deleted:</span>{" "}
          {summary.r2_objects_deleted ?? 0}
        </div>
      </div>
    </div>
  );
}

export function DsarOpsForm() {
  const [requestType, setRequestType] = useState<DsarType>("access");
  const [identifier, setIdentifier] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<DsarSummary | null>(null);

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
      setSummary(response.data.summary as unknown as DsarSummary);
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

          {summary && (
            <div className="mt-4 space-y-4">
              <Separator />
              <h2 className="text-lg font-semibold">Results</h2>

              {requestType === "deletion" ? (
                <DeletionSummary summary={summary} />
              ) : (
                <>
                  <MetadataSummary summary={summary} />

                  {summary.enriched_data ? (
                    <div className="space-y-4">
                      <h3 className="font-semibold">Enriched Data</h3>

                      {summary.enriched_data.photo && (
                        <PhotoSection photo={summary.enriched_data.photo} />
                      )}

                      <EmailsSection
                        emails={summary.enriched_data.emails}
                        verifiedEmails={summary.enriched_data.verified_emails}
                      />

                      {summary.enriched_data.handles &&
                        summary.enriched_data.handles.length > 0 && (
                          <HandlesSection handles={summary.enriched_data.handles} />
                        )}

                      {summary.enriched_data.business && (
                        <BusinessSection business={summary.enriched_data.business} />
                      )}

                      {summary.enriched_data.sources &&
                        summary.enriched_data.sources.length > 0 && (
                          <Card>
                            <CardHeader>
                              <CardTitle className="text-base">Data Sources</CardTitle>
                            </CardHeader>
                            <CardContent>
                              <div className="flex flex-wrap gap-2">
                                {summary.enriched_data.sources.map((source, idx) => (
                                  <Badge key={idx} variant="outline">
                                    {source}
                                  </Badge>
                                ))}
                              </div>
                            </CardContent>
                          </Card>
                        )}
                    </div>
                  ) : summary.job_count === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No enrichment data found for this identifier.
                    </p>
                  ) : null}
                </>
              )}
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
