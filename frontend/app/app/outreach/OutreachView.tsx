"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/console/EmptyState";
import {
  DraftOutreachDialog,
  type DraftOutreachConfirmPayload,
  OutreachDraftCard,
  useDraftOutreach,
  useOutreachMessages,
} from "@/features/outreach";

export function OutreachView() {
  const [draftOpen, setDraftOpen] = useState(false);
  const draftOutreach = useDraftOutreach();
  const { data, isLoading, isError } = useOutreachMessages({
    poll: draftOutreach.isSuccess || draftOutreach.isPending,
  });

  function handleConfirmDraft(payload: DraftOutreachConfirmPayload) {
    draftOutreach.mutate(
      {
        companyName: payload.companyName,
        documentId: payload.documentId,
        jobMatchId: payload.jobMatchId,
        jobDescription: payload.jobDescription,
        recipientRoleTitle: payload.recipientRoleTitle,
        messageType: payload.messageType,
        customInstruction: payload.customInstruction,
      },
      {
        onSuccess: () => {
          setDraftOpen(false);
          toast.success("Drafting outreach...", {
            description: "Your draft will appear here shortly.",
          });
        },
        onError: (error) =>
          toast.error("Couldn't start drafting outreach", { description: error.message }),
      },
    );
  }

  if (isLoading) return <div className="animate-pulse h-96 rounded-lg bg-muted" />;
  if (isError)
    return (
      <EmptyState
        title="Couldn't load your outreach drafts"
        description="Please try again shortly."
      />
    );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Outreach</h1>
        <Button onClick={() => setDraftOpen(true)}>New draft</Button>
      </div>

      {!data || data.messages.length === 0 ? (
        <EmptyState
          title="No outreach drafts yet"
          description="Generate a message with your résumé and an optional job description, or draft from the swipe deck."
          action={<Button onClick={() => setDraftOpen(true)}>New draft</Button>}
        />
      ) : (
        <div className="space-y-3">
          {data.messages.map((message) => (
            <OutreachDraftCard key={message.messageId} message={message} />
          ))}
        </div>
      )}

      <DraftOutreachDialog
        open={draftOpen}
        isPending={draftOutreach.isPending}
        onOpenChange={setDraftOpen}
        onConfirm={handleConfirmDraft}
      />
    </div>
  );
}
