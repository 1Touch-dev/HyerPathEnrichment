"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type {
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

interface DraftOutreachDialogProps {
  open: boolean;
  companyName: string | null;
  isPending?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (payload: {
    messageType: OutreachMessageType;
    customInstruction?: string;
    strategy: OutreachStrategy;
    referralContext?: string;
    roleType?: OutreachRoleType;
    seniority?: OutreachSeniority;
  }) => void;
}

/**
 * Module 4, Module G (§11.7): "draft type" selector shown as a confirmation step
 * between clicking "Draft outreach" (SwipeCard.tsx's onDraftOutreach, wired up in
 * SwipeDeckView.tsx — the actual trigger point for outreach generation today) and
 * enqueuing the draft-generation job, so the candidate picks which channel the
 * message is written for before the LLM call happens. Lives in the outreach feature
 * (rather than inside SwipeCard.tsx itself) so job-swipe's trigger button keeps its
 * existing "click -> call onDraftOutreach immediately" contract unchanged.
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
  companyName,
  isPending = false,
  onOpenChange,
  onConfirm,
}: DraftOutreachDialogProps) {
  const [messageType, setMessageType] = useState<OutreachMessageType>("email");
  const [customInstruction, setCustomInstruction] = useState("");
  const [strategy, setStrategy] = useState<OutreachStrategy>("direct_pitch");
  const [referralContext, setReferralContext] = useState("");
  const [roleType, setRoleType] = useState<OutreachRoleType | undefined>(undefined);
  const [seniority, setSeniority] = useState<OutreachSeniority | undefined>(undefined);

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
    onConfirm({
      messageType,
      customInstruction: messageType === "custom" ? customInstruction.trim() : undefined,
      strategy,
      referralContext: strategy === "warm_referral" ? referralContext.trim() : undefined,
      roleType: roleType && seniority ? roleType : undefined,
      seniority: roleType && seniority ? seniority : undefined,
    });
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
  const isReferralInvalid = strategy === "warm_referral" && referralContext.trim().length === 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Draft outreach{companyName ? ` to ${companyName}` : ""}</DialogTitle>
          <DialogDescription>
            Choose what kind of message to generate. LinkedIn and other non-email messages are
            copy-paste-only — they can&apos;t be sent from this app.
          </DialogDescription>
        </DialogHeader>

        {companyName && (
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
        )}

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
            <Label htmlFor="draft-outreach-custom-instruction">Instructions for this message</Label>
            <Textarea
              id="draft-outreach-custom-instruction"
              placeholder="e.g. Mention I found this role through a referral from..."
              value={customInstruction}
              onChange={(e) => setCustomInstruction(e.target.value)}
              rows={4}
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

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={isPending || isCustomInvalid || isReferralInvalid}
          >
            {isPending ? "Starting..." : "Draft outreach"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
