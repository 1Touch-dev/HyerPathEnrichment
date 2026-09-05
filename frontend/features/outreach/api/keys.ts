export const outreachKeys = {
  all: ["outreach"] as const,
  list: () => [...outreachKeys.all, "list"] as const,
};
