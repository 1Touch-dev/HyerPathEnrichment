export const interviewSchedulingKeys = {
  all: ["interview-scheduling"] as const,
  schedule: (matchId: string) => [...interviewSchedulingKeys.all, "schedule", matchId] as const,
};
