"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ResumeReference } from "@/features/documents/components/ResumeReference";
import { useMatches } from "@/features/job-matching/hooks/useMatches";
import { fetchDocuments } from "@/src/lib/api-client";
import type { DocumentSummary, OutreachMessageType } from "@/src/lib/types";

const MESSAGE_TYPE_OPTIONS: { value: OutreachMessageType; label: string }[] = [
  { value: "email", label: "Email" },
  { value: "linkedin", label: "LinkedIn message" },
  { value: "generic", label: "Generic message" },
  { value: "custom", label: "Custom" },
];

function isReadyDocument(doc: DocumentSummary): boolean {
  return doc.processingStatus === "completed" || doc.processingStatus === "embedded";
}

export type DraftOutreachConfirmPayload = {
  messageType: OutreachMessageType;
  customInstruction?: string;
  documentId: string;
  companyName: string;
  recipientRoleTitle?: string;
  jobMatchId?: string;
  jobDescription?: string;
};

interface DraftOutreachDialogProps {
  open: boolean;
  /** Prefill when drafting from a swipe/match card. */
  companyName?: string | null;
  jobMatchId?: string | null;
  recipientRoleTitle?: string | null;
  isPending?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (payload: DraftOutreachConfirmPayload) => void;
}

/**
 * Confirmation step before enqueuing outreach draft generation: message type,
 * résumé reference, and optional JD (tracked match or paste).
 */
export function DraftOutreachDialog({
  open,
  companyName: initialCompanyName = null,
  jobMatchId: initialJobMatchId = null,
  recipientRoleTitle: initialRoleTitle = null,
  isPending = false,
  onOpenChange,
  onConfirm,
}: DraftOutreachDialogProps) {
  const [messageType, setMessageType] = useState<OutreachMessageType>("email");
  const [customInstruction, setCustomInstruction] = useState("");
  const [companyName, setCompanyName] = useState(initialCompanyName ?? "");
  const [roleTitle, setRoleTitle] = useState(initialRoleTitle ?? "");
  const [jdSource, setJdSource] = useState<"tracked" | "paste" | "none">(
    initialJobMatchId ? "tracked" : "none",
  );
  const [selectedMatchId, setSelectedMatchId] = useState(initialJobMatchId ?? "");
  const [pastedJd, setPastedJd] = useState("");
  const [documentId, setDocumentId] = useState<string | undefined>(undefined);

  const { data: documents } = useQuery({
    queryKey: ["documents", "list"],
    queryFn: async () => (await fetchDocuments()).data,
    enabled: open,
  });

  const { data: matchesData, isLoading: matchesLoading } = useMatches(50, 0);

  const readyDocuments = useMemo(() => {
    const ready = (documents ?? []).filter(isReadyDocument);
    return [...ready].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    );
  }, [documents]);

  const latestDocument = readyDocuments[0];
  const selectedDocument =
    readyDocuments.find((doc) => doc.documentId === documentId) ?? latestDocument;

  useEffect(() => {
    if (!open) return;
    setCompanyName(initialCompanyName ?? "");
    setRoleTitle(initialRoleTitle ?? "");
    setSelectedMatchId(initialJobMatchId ?? "");
    setJdSource(initialJobMatchId ? "tracked" : "none");
    setPastedJd("");
    setMessageType("email");
    setCustomInstruction("");
  }, [open, initialCompanyName, initialJobMatchId, initialRoleTitle]);

  useEffect(() => {
    if (!latestDocument) {
      setDocumentId(undefined);
      return;
    }
    setDocumentId((current) => {
      if (current && readyDocuments.some((doc) => doc.documentId === current)) {
        return current;
      }
      return latestDocument.documentId;
    });
  }, [latestDocument, readyDocuments]);

  useEffect(() => {
    if (jdSource !== "tracked") return;
    const matches = matchesData?.matches ?? [];
    if (!selectedMatchId && matches.length > 0 && !initialJobMatchId) {
      setSelectedMatchId(matches[0].matchId);
    }
  }, [jdSource, matchesData, selectedMatchId, initialJobMatchId]);

  function handleOpenChange(next: boolean) {
    onOpenChange(next);
  }

  function handleConfirm() {
    if (!selectedDocument || !companyName.trim()) return;
    const payload: DraftOutreachConfirmPayload = {
      messageType,
      customInstruction: messageType === "custom" ? customInstruction.trim() : undefined,
      documentId: selectedDocument.documentId,
      companyName: companyName.trim(),
      recipientRoleTitle: roleTitle.trim() || undefined,
    };
    if (jdSource === "tracked" && selectedMatchId) {
      payload.jobMatchId = selectedMatchId;
    }
    if (jdSource === "paste" && pastedJd.trim().length >= 50) {
      payload.jobDescription = pastedJd.trim();
    }
    onConfirm(payload);
  }

  const isCustomInvalid = messageType === "custom" && customInstruction.trim().length === 0;
  const isPasteInvalid = jdSource === "paste" && pastedJd.trim().length < 50;
  const isTrackedInvalid = jdSource === "tracked" && !selectedMatchId && !initialJobMatchId;
  const canConfirm =
    Boolean(companyName.trim()) &&
    Boolean(selectedDocument) &&
    !isCustomInvalid &&
    !isPasteInvalid &&
    !isTrackedInvalid;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            Draft outreach{companyName.trim() ? ` to ${companyName.trim()}` : ""}
          </DialogTitle>
          <DialogDescription>
            Choose message type, résumé, and optional job description. LinkedIn and other non-email
            messages are copy-paste-only — they can&apos;t be sent from this app.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {!initialCompanyName ? (
            <div className="space-y-2">
              <Label htmlFor="draft-outreach-company">Company</Label>
              <Input
                id="draft-outreach-company"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g. Acme"
              />
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="draft-outreach-role">Role title (optional)</Label>
            <Input
              id="draft-outreach-role"
              value={roleTitle}
              onChange={(e) => setRoleTitle(e.target.value)}
              placeholder="e.g. Backend Engineer"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="draft-outreach-message-type">Message type</Label>
            <Select
              value={messageType}
              onValueChange={(value) => setMessageType(value as OutreachMessageType)}
            >
              <SelectTrigger id="draft-outreach-message-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MESSAGE_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {messageType === "custom" && (
            <div className="space-y-2">
              <Label htmlFor="draft-outreach-custom-instruction">
                Instructions for this message
              </Label>
              <Textarea
                id="draft-outreach-custom-instruction"
                placeholder="e.g. Mention I found this role through a referral from..."
                value={customInstruction}
                onChange={(e) => setCustomInstruction(e.target.value)}
                rows={3}
              />
            </div>
          )}

          <div className="space-y-2">
            <Label className="mb-1 block">Job description</Label>
            <RadioGroup
              value={jdSource}
              onValueChange={(value) => setJdSource(value as "tracked" | "paste" | "none")}
              className="grid gap-2"
            >
              <label className="flex cursor-pointer items-center gap-3 rounded-lg border p-3">
                <RadioGroupItem value="none" id="jd-none" />
                <Label htmlFor="jd-none" className="cursor-pointer font-normal">
                  No JD (company context only)
                </Label>
              </label>
              <label className="flex cursor-pointer items-center gap-3 rounded-lg border p-3">
                <RadioGroupItem value="tracked" id="jd-tracked" />
                <Label htmlFor="jd-tracked" className="cursor-pointer font-normal">
                  Tracked job
                </Label>
              </label>
              <label className="flex cursor-pointer items-center gap-3 rounded-lg border p-3">
                <RadioGroupItem value="paste" id="jd-paste" />
                <Label htmlFor="jd-paste" className="cursor-pointer font-normal">
                  Paste JD
                </Label>
              </label>
            </RadioGroup>

            {jdSource === "tracked" ? (
              initialJobMatchId ? (
                <p className="text-sm text-muted-foreground">
                  Using the job you drafted from on the swipe deck.
                </p>
              ) : matchesLoading ? (
                <p className="text-sm text-muted-foreground">Loading matches…</p>
              ) : (matchesData?.matches.length ?? 0) === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No tracked jobs yet.{" "}
                  <Link href="/app/matches" className="underline">
                    Go to Job matching
                  </Link>
                </p>
              ) : (
                <div>
                  <Label htmlFor="draft-tracked-job">Tracked job</Label>
                  <Select value={selectedMatchId} onValueChange={setSelectedMatchId}>
                    <SelectTrigger id="draft-tracked-job">
                      <SelectValue placeholder="Select a job" />
                    </SelectTrigger>
                    <SelectContent>
                      {matchesData?.matches.map((match) => (
                        <SelectItem key={match.matchId} value={match.matchId}>
                          {match.title} · {match.company}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )
            ) : null}

            {jdSource === "paste" ? (
              <div>
                <Label htmlFor="draft-pasted-jd">Job description</Label>
                <Textarea
                  id="draft-pasted-jd"
                  value={pastedJd}
                  onChange={(e) => setPastedJd(e.target.value)}
                  placeholder="Paste the full job description (at least 50 characters)."
                  rows={6}
                />
                {pastedJd.trim().length > 0 && pastedJd.trim().length < 50 ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Need {50 - pastedJd.trim().length} more characters.
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>

          {readyDocuments.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Upload a CV first to draft outreach.{" "}
              <Link href="/app/documents" className="underline">
                Go to Documents
              </Link>
            </p>
          ) : selectedDocument ? (
            <ResumeReference
              documents={readyDocuments}
              selectedId={selectedDocument.documentId}
              onSelect={setDocumentId}
            />
          ) : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={isPending || !canConfirm}>
            {isPending ? "Starting..." : "Draft outreach"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
