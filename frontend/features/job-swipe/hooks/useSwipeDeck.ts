import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSwipeDeck, submitSwipe } from "@/src/lib/api-client";
import type { SwipeDeck, SwipeDirection } from "@/src/lib/types";
import { jobSwipeKeys } from "../api/keys";

export function useSwipeDeck() {
  return useQuery({
    queryKey: jobSwipeKeys.deck(),
    queryFn: async () => (await fetchSwipeDeck()).data,
  });
}

export function useSubmitSwipe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ matchId, direction }: { matchId: string; direction: SwipeDirection }) =>
      submitSwipe(matchId, direction),
    // Optimistic removal — the card is already off-screen by the time this settles (see
    // SwipeCard.tsx). Rolling back on error would visually "un-swipe" a card the user
    // already dismissed, which is more confusing than leaving it gone and retrying silently.
    onMutate: async ({ matchId }) => {
      const previous = queryClient.getQueryData(jobSwipeKeys.deck());
      queryClient.setQueryData(jobSwipeKeys.deck(), (old: SwipeDeck | undefined) =>
        old ? { ...old, cards: old.cards.filter((c) => c.matchId !== matchId) } : old,
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      // Swallow the rollback deliberately (see comment above) — log only.
      console.error("Swipe failed to persist; deck already advanced client-side.", context);
    },
  });
}
