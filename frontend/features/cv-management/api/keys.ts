export const cvManagementKeys = {
  all: ["cv-management"] as const,
  completeness: (documentId: string) =>
    [...cvManagementKeys.all, "completeness", documentId] as const,
  feedback: (documentId: string) => [...cvManagementKeys.all, "feedback", documentId] as const,
  feedbackJob: (jobId: string) => [...cvManagementKeys.all, "feedback-job", jobId] as const,
};
