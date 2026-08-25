"use client";

import { useState } from "react";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import type { SourcedCandidateLead, SourcedLeadStatus } from "../api/sourcing-leads-client";
import {
  useCreateSourcedLead,
  useReviewSourcedLead,
  useSourcedLeads,
} from "../hooks/useSourcingLeads";

type StatusFilter = "all" | SourcedLeadStatus;

function statusBadgeVariant(status: SourcedCandidateLead["status"]) {
  if (status === "contacted") return "success" as const;
  if (status === "dismissed") return "warning" as const;
  return "outline" as const;
}

/**
 * Human-in-the-loop LinkedIn sourcing lead queue (machine-2/12). An intern who
 * manually browsed LinkedIn in their own logged-in session types in what they
 * observed below — every field in the entry form is plain manual text entry,
 * there is no "paste a profile URL and autofill" behavior anywhere on this
 * page, and nothing here ever calls linkedin.com or any third-party site (see
 * backend/app/modules/linkedin_sourcing/models.py's module docstring and
 * task-orchestration/machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md
 * for the legal-risk rationale this UI must not violate). Recruiters below
 * review the shared lead queue and move each lead to reviewed/contacted/dismissed.
 */
export function SourcingLeadsPanel() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("new");
  const status = statusFilter === "all" ? null : statusFilter;
  const { data: leads = [], isLoading } = useSourcedLeads(status);
  const createLead = useCreateSourcedLead();
  const reviewLead = useReviewSourcedLead();

  function handleReview(
    lead: SourcedCandidateLead,
    nextStatus: "reviewed" | "contacted" | "dismissed",
  ) {
    reviewLead.mutate({ id: lead.id, status: nextStatus });
  }

  return (
    <div className="flex flex-col gap-8">
      <LeadEntryForm
        isSubmitting={createLead.isPending}
        onSubmit={(input) => createLead.mutateAsync(input).then(() => undefined)}
      />

      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold tracking-tight">Recruiter review queue</h2>
          <Select
            value={statusFilter}
            onValueChange={(value) => setStatusFilter(value as StatusFilter)}
          >
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="new">New</SelectItem>
              <SelectItem value="reviewed">Reviewed</SelectItem>
              <SelectItem value="contacted">Contacted</SelectItem>
              <SelectItem value="dismissed">Dismissed</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {!leads.length && !isLoading ? (
          <EmptyState
            title="No sourced leads found"
            description="Try a different status filter, or wait for an intern to log a lead."
          />
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Headline</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Profile</TableHead>
                  <TableHead>Target role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leads.map((lead) => (
                  <TableRow key={lead.id}>
                    <TableCell>{lead.fullName}</TableCell>
                    <TableCell>{lead.headline ?? "—"}</TableCell>
                    <TableCell>{lead.location ?? "—"}</TableCell>
                    <TableCell>
                      <a
                        href={lead.linkedinProfileUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-primary underline"
                      >
                        {lead.linkedinProfileUrl}
                      </a>
                    </TableCell>
                    <TableCell>{lead.targetRole ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant={statusBadgeVariant(lead.status)}>{lead.status}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        {lead.status !== "reviewed" ? (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={reviewLead.isPending}
                            onClick={() => handleReview(lead, "reviewed")}
                          >
                            Mark reviewed
                          </Button>
                        ) : null}
                        {lead.status !== "contacted" ? (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={reviewLead.isPending}
                            onClick={() => handleReview(lead, "contacted")}
                          >
                            Mark contacted
                          </Button>
                        ) : null}
                        {lead.status !== "dismissed" ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={reviewLead.isPending}
                            onClick={() => handleReview(lead, "dismissed")}
                          >
                            Dismiss
                          </Button>
                        ) : null}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}

type LeadEntryFormProps = {
  isSubmitting: boolean;
  onSubmit: (input: {
    fullName: string;
    headline: string | null;
    location: string | null;
    linkedinProfileUrl: string;
    targetRole: string | null;
    notes: string | null;
  }) => Promise<void>;
};

const LINKEDIN_PROFILE_URL_PREFIX = "https://www.linkedin.com/";

/**
 * Every field below is typed by hand by the intern from what they personally
 * observed on a LinkedIn profile in their own browser session — there is no
 * "paste URL, autofill the rest" button or behavior, and no field is derived
 * from any network request. This is a deliberate, non-negotiable constraint
 * (see this file's module docstring above).
 */
function LeadEntryForm({ isSubmitting, onSubmit }: LeadEntryFormProps) {
  const [fullName, setFullName] = useState("");
  const [headline, setHeadline] = useState("");
  const [location, setLocation] = useState("");
  const [linkedinProfileUrl, setLinkedinProfileUrl] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const trimmedUrl = linkedinProfileUrl.trim();
  const canSubmit =
    fullName.trim().length > 0 && trimmedUrl.startsWith(LINKEDIN_PROFILE_URL_PREFIX);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!fullName.trim()) {
      setError("Full name is required.");
      return;
    }
    if (!trimmedUrl.startsWith(LINKEDIN_PROFILE_URL_PREFIX)) {
      setError(`LinkedIn profile URL must start with ${LINKEDIN_PROFILE_URL_PREFIX}`);
      return;
    }

    try {
      await onSubmit({
        fullName: fullName.trim(),
        headline: headline.trim() || null,
        location: location.trim() || null,
        linkedinProfileUrl: trimmedUrl,
        targetRole: targetRole.trim() || null,
        notes: notes.trim() || null,
      });
      setFullName("");
      setHeadline("");
      setLocation("");
      setLinkedinProfileUrl("");
      setTargetRole("");
      setNotes("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to log this lead.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-lg border p-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight">Log a sourced lead</h2>
        <p className="text-sm text-muted-foreground">
          Type in exactly what you observed while manually browsing LinkedIn in your own logged-in
          session. Nothing on this form is auto-filled — there is no URL-paste-and-autofill feature
          here by design.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="lead-full-name">Full name *</Label>
          <Input
            id="lead-full-name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Jane Candidate"
            required
          />
        </div>
        <div>
          <Label htmlFor="lead-headline">Headline / current role</Label>
          <Input
            id="lead-headline"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            placeholder="Senior Backend Engineer at Acme"
          />
        </div>
        <div>
          <Label htmlFor="lead-location">Location</Label>
          <Input
            id="lead-location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Berlin, Germany"
          />
        </div>
        <div>
          <Label htmlFor="lead-target-role">Target role</Label>
          <Input
            id="lead-target-role"
            value={targetRole}
            onChange={(e) => setTargetRole(e.target.value)}
            placeholder="Backend Engineer"
          />
        </div>
        <div className="sm:col-span-2">
          <Label htmlFor="lead-profile-url">LinkedIn profile URL *</Label>
          <Input
            id="lead-profile-url"
            value={linkedinProfileUrl}
            onChange={(e) => setLinkedinProfileUrl(e.target.value)}
            placeholder="https://www.linkedin.com/in/jane-candidate"
            required
          />
        </div>
        <div className="sm:col-span-2">
          <Label htmlFor="lead-notes">Notes</Label>
          <Textarea
            id="lead-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="What you noticed on their profile, why they might be a fit, etc."
          />
        </div>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div>
        <Button type="submit" disabled={!canSubmit || isSubmitting}>
          {isSubmitting ? "Logging…" : "Log lead"}
        </Button>
      </div>
    </form>
  );
}
