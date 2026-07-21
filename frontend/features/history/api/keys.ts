export const jobKeys = {
  all: ["jobs"] as const,
  list: (limit: number, offset: number) => [...jobKeys.all, "list", { limit, offset }] as const,
  metrics: () => [...jobKeys.all, "metrics"] as const,
};
