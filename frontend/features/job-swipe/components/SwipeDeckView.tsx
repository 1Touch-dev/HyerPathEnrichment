"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/console/EmptyState";
import {
  DraftOutreachDialog,
  type DraftOutreachConfirmPayload,
  useDraftOutreachForMatch,
} from "@/features/outreach";
import type { SwipeDirection } from "@/src/lib/types";
import { useSubmitSwipe, useSwipeDeck } from "../hooks/useSwipeDeck";
import { SwipeCard } from "./SwipeCard";

const MAX_STACKED_CARDS = 3;

export function SwipeDeckView() {
  const { data, isLoading, isError, refetch, isRefetching } = useSwipeDeck();
  const submitSwipe = useSubmitSwipe();
  const draftOutreach = useDraftOutreachForMatch();
  const [draftTarget, setDraftTarget] = useState<{
    matchId: string;
    companyName: string;
    title: string;
  } | null>(null);

  if (isLoading)
    return (
      <div className="h-[32rem] animate-pulse rounded-2xl border border-border/70 bg-surface shadow-panel" />
    );
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
    const card = data?.cards.find((c) => c.matchId === matchId);
    setDraftTarget({ matchId, companyName, title: card?.title ?? "" });
  }

  function handleConfirmDraft(payload: DraftOutreachConfirmPayload) {
    if (!draftTarget) return;
    draftOutreach.mutate(
      {
        companyName: payload.companyName,
        documentId: payload.documentId,
        jobMatchId: payload.jobMatchId ?? draftTarget.matchId,
        jobDescription: payload.jobDescription,
        recipientRoleTitle: payload.recipientRoleTitle || draftTarget.title || undefined,
        messageType: payload.messageType,
        customInstruction: payload.customInstruction,
        strategy: payload.strategy,
        referralContext: payload.referralContext,
        roleType: payload.roleType,
        seniority: payload.seniority,
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
    <div className="flex flex-col items-center gap-4">
      <div className="flex flex-wrap items-center justify-center gap-2 text-center text-sm text-muted-foreground">
        <Badge variant="success">Interested</Badge>
        <Badge variant="outline">Pass</Badge>
        <Badge variant="info">Super like</Badge>
        <span>Draft outreach from the top card any time.</span>
      </div>

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
      </div>

      <p className="max-w-md text-center text-sm text-muted-foreground">
        The swipe order stays connected to your real match data, so you can jump back to the list
        view or outreach queue without losing state.
      </p>

      <DraftOutreachDialog
        open={draftTarget !== null}
        companyName={draftTarget?.companyName ?? null}
        jobMatchId={draftTarget?.matchId ?? null}
        recipientRoleTitle={draftTarget?.title ?? null}
        isPending={draftOutreach.isPending}
        onOpenChange={(open) => {
          if (!open) setDraftTarget(null);
        }}
        onConfirm={handleConfirmDraft}
      />
    </div>
  );
}
