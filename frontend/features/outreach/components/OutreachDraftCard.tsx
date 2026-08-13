"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { OutreachMessage } from "@/src/lib/types";
import { useEditOutreachDraft, useSendOutreach } from "../hooks/useOutreach";

interface OutreachDraftCardProps {
  message: OutreachMessage;
}

export function OutreachDraftCard({ message }: OutreachDraftCardProps) {
  const editDraft = useEditOutreachDraft();
  const sendMessage = useSendOutreach();
  const [subject, setSubject] = useState(message.subject);
  const [body, setBody] = useState(message.body);
  const isDirty = subject !== message.subject || body !== message.body;

  const canEdit = message.status === "draft";

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium">{message.companyName}</h3>
          {message.recipientRole && (
            <p className="text-sm text-muted-foreground">{message.recipientRole}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {message.companyContextSource === "none" && (
            <Badge variant="outline" title="No live company research was available for this draft.">
              Generic draft
            </Badge>
          )}
          <Badge variant={message.status === "sent" ? "default" : "outline"}>{message.status}</Badge>
        </div>
      </div>

      <Input value={subject} onChange={(e) => setSubject(e.target.value)} disabled={!canEdit} />
      <Textarea value={body} onChange={(e) => setBody(e.target.value)} disabled={!canEdit} rows={8} />

      {canEdit && (
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
            onClick={() => sendMessage.mutate(message.messageId)}
            disabled={sendMessage.isPending || isDirty}
            title={isDirty ? "Save your changes before sending" : undefined}
          >
            {sendMessage.isPending ? "Sending..." : "Send"}
          </Button>
        </div>
      )}
    </div>
  );
}
