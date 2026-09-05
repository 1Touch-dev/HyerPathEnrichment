"use client";

import { useState } from "react";
import { Copy } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { OutreachMessage } from "@/src/lib/types";
import { copyToClipboard } from "@/src/lib/utils";
import { useEditOutreachDraft, useSendOutreach } from "../hooks/useOutreach";

interface OutreachDraftCardProps {
  message: OutreachMessage;
}

// Mirrors backend/app/core/config.py's `outreach_linkedin_inmail_subject_max_chars` /
// `outreach_linkedin_inmail_body_max_chars` defaults (§11.9) — not exposed to the
// frontend via any settings endpoint today, so hardcoded here to match.
const LINKEDIN_SUBJECT_MAX_CHARS = 200;
const LINKEDIN_BODY_MAX_CHARS = 1900;
// Amber kicks in at 1500/1900 of the limit (§11.7); applied proportionally to the
// subject's shorter limit too, so both counters turn amber/red at the same "fraction
// of the limit used", not the same absolute character count.
const LINKEDIN_COUNTER_AMBER_RATIO = 1500 / 1900;

function counterColorClass(length: number, max: number): string {
  if (length > max) return "text-red-600 dark:text-red-500";
  if (length > max * LINKEDIN_COUNTER_AMBER_RATIO) return "text-amber-600 dark:text-amber-500";
  return "text-muted-foreground";
}

export function OutreachDraftCard({ message }: OutreachDraftCardProps) {
  const editDraft = useEditOutreachDraft();
  const sendMessage = useSendOutreach();
  const [subject, setSubject] = useState(message.subject);
  const [body, setBody] = useState(message.body);
  const isDirty = subject !== message.subject || body !== message.body;

  const canEdit = message.status === "draft";
  const isEmail = message.messageType === "email";
  const isLinkedIn = message.messageType === "linkedin";

  function handleSend() {
    // Non-email channels have no send-as-the-candidate API (§11.1/§11.6) — "sending"
    // here means copying the body so the candidate can paste it into LinkedIn/their
    // messaging app themselves, then marking it as sent.
    if (!isEmail) {
      void copyToClipboard(body);
    }
    sendMessage.mutate(message.messageId);
  }

  const editErrorMessage =
    editDraft.isError && editDraft.error instanceof Error
      ? editDraft.error.message
      : editDraft.isError
        ? "Couldn't save your changes."
        : null;

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium">{message.companyName}</h3>
          {message.recipientRoleTitle && (
            <p className="text-sm text-muted-foreground">{message.recipientRoleTitle}</p>
          )}
        </div>
        <Badge variant={message.status === "sent" ? "default" : "outline"}>{message.status}</Badge>
      </div>

      <div className="space-y-1">
        <Input value={subject} onChange={(e) => setSubject(e.target.value)} disabled={!canEdit} />
        {isLinkedIn && canEdit && (
          <p className={`text-xs ${counterColorClass(subject.length, LINKEDIN_SUBJECT_MAX_CHARS)}`}>
            {subject.length} / {LINKEDIN_SUBJECT_MAX_CHARS}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <div className="flex items-start gap-2">
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            disabled={!canEdit}
            rows={8}
            className="flex-1"
          />
          {!isEmail && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Copy message to clipboard"
              onClick={() => copyToClipboard(body)}
            >
              <Copy className="h-4 w-4" />
            </Button>
          )}
        </div>
        {isLinkedIn && canEdit && (
          <p className={`text-xs ${counterColorClass(body.length, LINKEDIN_BODY_MAX_CHARS)}`}>
            {body.length} / {LINKEDIN_BODY_MAX_CHARS}
          </p>
        )}
      </div>

      {!isEmail && (
        <p className="text-xs text-muted-foreground">
          LinkedIn/DMs can&apos;t be sent from here — copy this and paste it into LinkedIn/your
          messaging app yourself.
        </p>
      )}

      {canEdit && (
        <div className="space-y-2">
          {editErrorMessage && (
            <Alert variant="destructive">
              <AlertDescription>{editErrorMessage}</AlertDescription>
            </Alert>
          )}
          <div className="flex justify-end gap-2">
            {isDirty && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => editDraft.mutate({ messageId: message.messageId, subject, body })}
                disabled={editDraft.isPending}
              >
                Save changes
              </Button>
            )}
            <Button
              size="sm"
              onClick={handleSend}
              disabled={sendMessage.isPending || isDirty}
              title={isDirty ? "Save your changes before sending" : undefined}
            >
              {sendMessage.isPending
                ? isEmail
                  ? "Sending..."
                  : "Copying..."
                : isEmail
                  ? "Send"
                  : "Copy & mark as sent"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
