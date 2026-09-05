export const jobMatchingKeys = {
  all: ["job-matching"] as const,
  preferences: () => [...jobMatchingKeys.all, "preferences"] as const,
  matches: (limit: number, offset: number) =>
    [...jobMatchingKeys.all, "matches", limit, offset] as const,
};
