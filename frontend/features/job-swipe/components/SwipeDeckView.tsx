"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/console/EmptyState";
import { DraftOutreachDialog, useDraftOutreachForMatch } from "@/features/outreach";
import type { OutreachMessageType, SwipeDirection } from "@/src/lib/types";
import { useSubmitSwipe, useSwipeDeck } from "../hooks/useSwipeDeck";
import { SwipeCard } from "./SwipeCard";

const MAX_STACKED_CARDS = 3;

export function SwipeDeckView() {
  const { data, isLoading, isError, refetch, isRefetching } = useSwipeDeck();
  const submitSwipe = useSubmitSwipe();
  const draftOutreach = useDraftOutreachForMatch();
  const [draftTarget, setDraftTarget] = useState<{ matchId: string; companyName: string } | null>(
    null,
  );

  if (isLoading) return <div className="animate-pulse h-[32rem] rounded-2xl bg-muted" />;
  if (isError)
    return <EmptyState title="Couldn't load your deck" description="Please try again shortly." />;
  if (!data || data.cards.length === 0) {
    // `hasMore` reflects the backend's unswiped-match count at the time of the last fetch
    // (backend/app/modules/job_swipe/service.py's `_DECK_PAGE_SIZE` paging) — once the visible
    // page is exhausted client-side, refetching naturally returns the next page since already-
    // swiped matches are excluded server-side (no offset/cursor needed).
    if (data?.hasMore) {
      return (
        <EmptyState
          title="You're caught up on this page"
          description="There are more matches waiting — load the next batch."
          action={
            <Button onClick={() => refetch()} disabled={isRefetching}>
              {isRefetching ? "Loading..." : "Load more"}
            </Button>
          }
        />
      );
    }
    return (
      <EmptyState
        title="No new matches to review"
        description="Check back after your next job scan, or adjust your preferences."
      />
    );
  }

  const visibleCards = data.cards.slice(0, MAX_STACKED_CARDS);

  function handleSwipe(matchId: string, direction: SwipeDirection) {
    submitSwipe.mutate({ matchId, direction });
  }

  function handleDraftOutreach(matchId: string, companyName: string) {
    setDraftTarget({ matchId, companyName });
  }

  function handleConfirmDraft(payload: {
    messageType: OutreachMessageType;
    customInstruction?: string;
  }) {
    if (!draftTarget) return;
    draftOutreach.mutate(
      {
        companyName: draftTarget.companyName,
        jobMatchId: draftTarget.matchId,
        messageType: payload.messageType,
        customInstruction: payload.customInstruction,
      },
      {
        onSuccess: () => {
          setDraftTarget(null);
          toast.success("Drafting outreach...", {
            description: "Your draft will appear on the Outreach page shortly.",
          });
        },
        onError: (error) =>
          toast.error("Couldn't start drafting outreach", { description: error.message }),
      },
    );
  }

  return (
    <div className="relative mx-auto h-[32rem] w-full max-w-sm">
      {visibleCards
        .slice()
        .reverse()
        .map((card, reverseIndex) => {
          const index = visibleCards.length - 1 - reverseIndex;
          return (
            <SwipeCard
              key={card.matchId}
              card={card}
              isTop={index === 0}
              onSwiped={(direction) => handleSwipe(card.matchId, direction)}
              onDraftOutreach={handleDraftOutreach}
            />
          );
        })}
      <DraftOutreachDialog
        open={draftTarget !== null}
        companyName={draftTarget?.companyName ?? null}
        isPending={draftOutreach.isPending}
        onOpenChange={(open) => {
          if (!open) setDraftTarget(null);
        }}
        onConfirm={handleConfirmDraft}
      />
    </div>
  );
}
