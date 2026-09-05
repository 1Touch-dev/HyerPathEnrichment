export const documentKeys = {
  all: ["documents"] as const,
  list: (limit?: number) =>
    limit === undefined
      ? ([...documentKeys.all, "list"] as const)
      : ([...documentKeys.all, "list", limit] as const),
  detail: (documentId: string) => [...documentKeys.all, "detail", documentId] as const,
  job: (jobId: string) => [...documentKeys.all, "job", jobId] as const,
  cvData: (documentId: string) => [...documentKeys.all, "cv-data", documentId] as const,
  search: (query: string, limit: number) => [...documentKeys.all, "search", query, limit] as const,
};
