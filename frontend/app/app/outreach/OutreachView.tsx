"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  ShellPageHeader,
  ShellPageHeaderActions,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
  ShellSection,
  ShellSectionHeader,
  ShellSectionHeaderContent,
  ShellSectionHeaderDescription,
  ShellSectionHeaderTitle,
} from "@/components/layout/ShellPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/console/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  const messages = data?.messages ?? [];
  const draftCount = messages.filter((message) => message.status === "draft").length;
  const sentCount = messages.filter((message) => message.status === "sent").length;

  const header = (
    <ShellPageHeader>
      <ShellPageHeaderContent>
        <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
        <ShellPageHeaderTitle>Outreach</ShellPageHeaderTitle>
        <ShellPageHeaderDescription>
          Draft messages, tighten the tone, and keep your next follow-up visible without mixing
          candidate outreach into a staff-style queue.
        </ShellPageHeaderDescription>
      </ShellPageHeaderContent>
      <ShellPageHeaderActions className="items-start sm:items-center">
        <Badge variant="outline">
          {draftOutreach.isPending ? "Drafting in progress" : "Ready"}
        </Badge>
        <Button onClick={() => setDraftOpen(true)}>New draft</Button>
      </ShellPageHeaderActions>
    </ShellPageHeader>
  );

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

  if (isLoading) {
    return (
      <div className="space-y-6">
        {header}
        <div className="grid gap-4 md:grid-cols-3">
          <div className="animate-pulse rounded-lg bg-muted h-28" />
          <div className="animate-pulse rounded-lg bg-muted h-28" />
          <div className="animate-pulse rounded-lg bg-muted h-28" />
        </div>
        <div className="animate-pulse h-96 rounded-lg bg-muted" />
      </div>
    );
  }
  if (isError)
    return (
      <div className="space-y-6">
        {header}
        <EmptyState
          title="Couldn't load your outreach drafts"
          description="Please try again shortly."
        />
      </div>
    );

  return (
    <div className="space-y-6">
      {header}

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Drafts</p>
            <CardTitle className="text-3xl text-primary">{draftCount}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Messages you can still edit before sending or copying.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Sent</p>
            <CardTitle className="text-3xl text-primary">{sentCount}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Outreach you have already sent or copied out.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Resume context</p>
            <CardTitle className="text-3xl text-primary">
              {messages.length > 0 ? "On" : "Ready"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            New drafts can pull from your resume and optional job context.
          </CardContent>
        </Card>
      </div>

      {!data || messages.length === 0 ? (
        <ShellSection surface="muted">
          <EmptyState
            title="No outreach drafts yet"
            description="Generate a message with your résumé and an optional job description, or draft from the swipe deck."
            action={<Button onClick={() => setDraftOpen(true)}>New draft</Button>}
          />
        </ShellSection>
      ) : (
        <ShellSection>
          <ShellSectionHeader>
            <ShellSectionHeaderContent>
              <ShellSectionHeaderTitle>Your draft queue</ShellSectionHeaderTitle>
              <ShellSectionHeaderDescription>
                Save edits first, then send emails directly or copy other message types into the
                destination channel yourself.
              </ShellSectionHeaderDescription>
            </ShellSectionHeaderContent>
          </ShellSectionHeader>

          <div className="space-y-3">
            {messages.map((message) => (
              <OutreachDraftCard key={message.messageId} message={message} />
            ))}
          </div>
        </ShellSection>
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
