export const enrichKeys = {
  all: ["enrich"] as const,
  jobs: () => [...enrichKeys.all, "jobs"] as const,
  job: (id: string) => [...enrichKeys.all, "job", id] as const,
};
