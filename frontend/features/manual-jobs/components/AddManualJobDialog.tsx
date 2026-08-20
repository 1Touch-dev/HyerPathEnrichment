"use client";

import { FormEvent, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
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
import { Textarea } from "@/components/ui/textarea";
import { useCreateManualJobEntry } from "../hooks/useCreateManualJobEntry";

interface AddManualJobDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function isValidUrl(value: string): boolean {
  try {
    new URL(value);
    return true;
  } catch {
    return false;
  }
}

/**
 * v1 is create-only (§14 non-goal: "Editing or deleting a manual job entry") — this
 * dialog only ever POSTs a new entry; there is deliberately no edit mode or initial-
 * value prop, and no delete affordance anywhere near it.
 */
export function AddManualJobDialog({ open, onOpenChange }: AddManualJobDialogProps) {
  const createEntry = useCreateManualJobEntry();
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [sourceLabel, setSourceLabel] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  function resetForm() {
    setTitle("");
    setCompany("");
    setLocation("");
    setSourceLabel("");
    setSourceUrl("");
    setNotes("");
    setFormError(null);
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      resetForm();
      createEntry.reset();
    }
    onOpenChange(nextOpen);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!title.trim() || !company.trim()) {
      setFormError("Title and company are required.");
      return;
    }
    if (sourceUrl.trim() && !isValidUrl(sourceUrl.trim())) {
      setFormError("Please enter a valid URL (e.g. https://example.com/careers/123).");
      return;
    }

    setFormError(null);
    createEntry.mutate(
      {
        title: title.trim(),
        company: company.trim(),
        location: location.trim() ? location.trim() : null,
        sourceLabel: sourceLabel.trim() ? sourceLabel.trim() : null,
        sourceUrl: sourceUrl.trim() ? sourceUrl.trim() : null,
        notes: notes.trim() ? notes.trim() : null,
      },
      {
        onSuccess: () => handleOpenChange(false),
        // On failure the dialog intentionally stays open (no onError handler closes
        // it) — createEntry.isError below renders an inline form-level error instead,
        // and none of the typed field state is cleared, per §15.5's error-state spec.
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Add a job manually</DialogTitle>
            <DialogDescription>
              Track a job you found elsewhere — we&apos;ll add it to your Applications board.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="manual-job-title">Job title</Label>
              <Input
                id="manual-job-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Senior Software Engineer"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="manual-job-company">Company</Label>
              <Input
                id="manual-job-company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Acme Inc."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="manual-job-location">Location</Label>
              <Input
                id="manual-job-location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Remote, or a city"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="manual-job-source-label">Where did you find it?</Label>
              <Input
                id="manual-job-source-label"
                value={sourceLabel}
                onChange={(e) => setSourceLabel(e.target.value)}
                placeholder="LinkedIn, company site, referral…"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="manual-job-source-url">Job posting URL</Label>
              <Input
                id="manual-job-source-url"
                type="url"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://example.com/careers/123"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="manual-job-notes">Notes</Label>
              <Textarea
                id="manual-job-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Paste the job description or any notes you want to keep…"
              />
            </div>

            {(formError || createEntry.isError) && (
              <p className="text-sm text-destructive" role="alert">
                {formError ?? "Couldn't add this job. Please try again."}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={createEntry.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createEntry.isPending}>
              {createEntry.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              {createEntry.isPending ? "Adding…" : "Add job"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
