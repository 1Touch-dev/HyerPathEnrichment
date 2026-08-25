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
import type {
  DocumentSummary,
  OutreachCompanyTierValue,
  OutreachMessageType,
  OutreachRoleType,
  OutreachSeniority,
  OutreachStrategy,
} from "@/src/lib/types";
import { useCompanyTier, useSetCompanyTier } from "../hooks/useOutreach";

const MESSAGE_TYPE_OPTIONS: { value: OutreachMessageType; label: string }[] = [
  { value: "email", label: "Email" },
  { value: "linkedin", label: "LinkedIn message" },
  { value: "generic", label: "Generic message" },
  { value: "custom", label: "Custom" },
];

const STRATEGY_OPTIONS: { value: OutreachStrategy; label: string }[] = [
  { value: "direct_pitch", label: "Direct pitch" },
  { value: "value_first", label: "Value first" },
  { value: "curiosity", label: "Curiosity" },
  { value: "warm_referral", label: "Warm referral" },
];

const ROLE_TYPE_OPTIONS: { value: OutreachRoleType; label: string }[] = [
  { value: "technical", label: "Technical" },
  { value: "non_technical", label: "Non-technical" },
];

const SENIORITY_OPTIONS: { value: OutreachSeniority; label: string }[] = [
  { value: "junior", label: "Junior" },
  { value: "senior", label: "Senior" },
];

const COMPANY_TIER_OPTIONS: { value: OutreachCompanyTierValue; label: string }[] = [
  { value: "premium", label: "Premium" },
  { value: "outsourcing", label: "Outsourcing" },
];

/** Sentinel used for the "unset" option of an otherwise-optional `<Select>` — Radix's
 * `Select.Item` cannot use an empty string as a value, so `undefined` state is
 * represented by this sentinel at the UI layer and converted back to `undefined`
 * before reaching `onConfirm`/the mutation payload. */
const UNSET = "__unset__";

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
  strategy: OutreachStrategy;
  referralContext?: string;
  roleType?: OutreachRoleType;
  seniority?: OutreachSeniority;
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
 *
 * machine-2/03: also hosts the `strategy`/`roleType`/`seniority` drafting-approach
 * selectors and the manual, per-employer "Company tier" control — this dialog is
 * the surface that already renders `companyName` most prominently to a recruiter
 * about to draft outreach (the dialog title itself), so the tier control lives here
 * rather than on `SwipeCard.tsx`'s card, per the track spec's own guidance to pick
 * whichever existing surface fits best rather than adding a new screen.
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
  const [strategy, setStrategy] = useState<OutreachStrategy>("direct_pitch");
  const [referralContext, setReferralContext] = useState("");
  const [roleType, setRoleType] = useState<OutreachRoleType | undefined>(undefined);
  const [seniority, setSeniority] = useState<OutreachSeniority | undefined>(undefined);

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

  const companyTier = useCompanyTier(companyName);
  const setCompanyTierMutation = useSetCompanyTier();
  const [tierValue, setTierValue] = useState<OutreachCompanyTierValue | undefined>(undefined);

  // machine-2/03: pre-fill the tier select from the previously-set value for this
  // company whenever the dialog opens for a (possibly different) company, so a
  // tier set on an earlier draft to the same employer persists visibly here.
  useEffect(() => {
    if (open) {
      setTierValue(companyTier.data?.tier);
    }
  }, [open, companyTier.data?.tier]);

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
    if (!next) {
      setMessageType("email");
      setCustomInstruction("");
      setStrategy("direct_pitch");
      setReferralContext("");
      setRoleType(undefined);
      setSeniority(undefined);
    }
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
      strategy,
      referralContext: strategy === "warm_referral" ? referralContext.trim() : undefined,
      roleType: roleType && seniority ? roleType : undefined,
      seniority: roleType && seniority ? seniority : undefined,
    };
    if (jdSource === "tracked" && selectedMatchId) {
      payload.jobMatchId = selectedMatchId;
    }
    if (jdSource === "paste" && pastedJd.trim().length >= 50) {
      payload.jobDescription = pastedJd.trim();
    }
    onConfirm(payload);
  }

  function handleTierChange(value: string) {
    if (!companyName) return;
    const nextTier = value === UNSET ? undefined : (value as OutreachCompanyTierValue);
    setTierValue(nextTier);
    if (nextTier) {
      setCompanyTierMutation.mutate({ companyName, tier: nextTier });
    }
  }

  const isCustomInvalid = messageType === "custom" && customInstruction.trim().length === 0;
  const isPasteInvalid = jdSource === "paste" && pastedJd.trim().length < 50;
  const isTrackedInvalid = jdSource === "tracked" && !selectedMatchId && !initialJobMatchId;
  const isReferralInvalid = strategy === "warm_referral" && referralContext.trim().length === 0;
  const canConfirm =
    Boolean(companyName.trim()) &&
    Boolean(selectedDocument) &&
    !isCustomInvalid &&
    !isPasteInvalid &&
    !isTrackedInvalid &&
    !isReferralInvalid;

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

          {companyName.trim() ? (
            <div className="space-y-2">
              <Label htmlFor="draft-outreach-company-tier">Company tier</Label>
              <Select value={tierValue ?? UNSET} onValueChange={handleTierChange}>
                <SelectTrigger id="draft-outreach-company-tier">
                  <SelectValue placeholder="Unset" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={UNSET}>Unset</SelectItem>
                  {COMPANY_TIER_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
            <Label htmlFor="draft-outreach-strategy">Strategy</Label>
            <Select
              value={strategy}
              onValueChange={(value) => setStrategy(value as OutreachStrategy)}
            >
              <SelectTrigger id="draft-outreach-strategy">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STRATEGY_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {strategy === "warm_referral" && (
            <div className="space-y-2">
              <Label htmlFor="draft-outreach-referral-context">Referral context</Label>
              <Textarea
                id="draft-outreach-referral-context"
                placeholder="e.g. Referred by Jane Doe, who works on the platform team..."
                value={referralContext}
                onChange={(e) => setReferralContext(e.target.value)}
                rows={4}
              />
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="draft-outreach-role-type">Role type (optional)</Label>
            <Select
              value={roleType ?? UNSET}
              onValueChange={(value) =>
                setRoleType(value === UNSET ? undefined : (value as OutreachRoleType))
              }
            >
              <SelectTrigger id="draft-outreach-role-type">
                <SelectValue placeholder="Unset" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={UNSET}>Unset</SelectItem>
                {ROLE_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="draft-outreach-seniority">Seniority (optional)</Label>
            <Select
              value={seniority ?? UNSET}
              onValueChange={(value) =>
                setSeniority(value === UNSET ? undefined : (value as OutreachSeniority))
              }
            >
              <SelectTrigger id="draft-outreach-seniority">
                <SelectValue placeholder="Unset" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={UNSET}>Unset</SelectItem>
                {SENIORITY_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

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
