"use client";

import { EmptyState } from "@/components/console/EmptyState";
import type { SwipeDirection } from "@/src/lib/types";
import { useSubmitSwipe, useSwipeDeck } from "../hooks/useSwipeDeck";
import { SwipeCard } from "./SwipeCard";

const MAX_STACKED_CARDS = 3;

export function SwipeDeckView() {
  const { data, isLoading, isError } = useSwipeDeck();
  const submitSwipe = useSubmitSwipe();

  if (isLoading) return <div className="animate-pulse h-[32rem] rounded-2xl bg-muted" />;
  if (isError) return <EmptyState title="Couldn't load your deck" description="Please try again shortly." />;
  if (!data || data.cards.length === 0) {
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
            />
          );
        })}
    </div>
  );
}
