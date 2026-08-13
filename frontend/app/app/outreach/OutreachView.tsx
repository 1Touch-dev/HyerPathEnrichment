"use client";

import { EmptyState } from "@/components/console/EmptyState";
import { OutreachDraftCard, useOutreachMessages } from "@/features/outreach";

export function OutreachView() {
  const { data, isLoading, isError } = useOutreachMessages();

  if (isLoading) return <div className="animate-pulse h-96 rounded-lg bg-muted" />;
  if (isError) return <EmptyState title="Couldn't load your outreach drafts" description="Please try again shortly." />;
  if (!data || data.messages.length === 0) {
    return (
      <EmptyState
        title="No outreach drafts yet"
        description={'Draft outreach from a job\u2019s "why we matched you" card on your swipe deck or matches list.'}
      />
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Outreach</h1>
      <div className="space-y-3">
        {data.messages.map((message) => (
          <OutreachDraftCard key={message.messageId} message={message} />
        ))}
      </div>
    </div>
  );
}
