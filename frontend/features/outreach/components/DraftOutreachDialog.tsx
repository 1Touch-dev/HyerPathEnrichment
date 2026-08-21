"use client";

import { useState } from "react";
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
import type { OutreachMessageType } from "@/src/lib/types";

const MESSAGE_TYPE_OPTIONS: { value: OutreachMessageType; label: string }[] = [
  { value: "email", label: "Email" },
  { value: "linkedin", label: "LinkedIn message" },
  { value: "generic", label: "Generic message" },
  { value: "custom", label: "Custom" },
];

interface DraftOutreachDialogProps {
  open: boolean;
  companyName: string | null;
  isPending?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (payload: { messageType: OutreachMessageType; customInstruction?: string }) => void;
}

/**
 * Module 4, Module G (§11.7): "draft type" selector shown as a confirmation step
 * between clicking "Draft outreach" (SwipeCard.tsx's onDraftOutreach, wired up in
 * SwipeDeckView.tsx — the actual trigger point for outreach generation today) and
 * enqueuing the draft-generation job, so the candidate picks which channel the
 * message is written for before the LLM call happens. Lives in the outreach feature
 * (rather than inside SwipeCard.tsx itself) so job-swipe's trigger button keeps its
 * existing "click -> call onDraftOutreach immediately" contract unchanged.
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

  function handleOpenChange(next: boolean) {
    if (!next) {
      setMessageType("email");
      setCustomInstruction("");
    }
    onOpenChange(next);
  }

  function handleConfirm() {
    onConfirm({
      messageType,
      customInstruction: messageType === "custom" ? customInstruction.trim() : undefined,
    });
  }

  const isCustomInvalid = messageType === "custom" && customInstruction.trim().length === 0;

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

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={isPending || isCustomInvalid}>
            {isPending ? "Starting..." : "Draft outreach"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
