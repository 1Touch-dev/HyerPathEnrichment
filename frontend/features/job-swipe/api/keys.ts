export const jobSwipeKeys = {
  all: ["job-swipe"] as const,
  deck: () => [...jobSwipeKeys.all, "deck"] as const,
};
