export const jdPracticeKeys = {
  all: ["jd-practice"] as const,
  questions: (jobMatchId: string) => [...jdPracticeKeys.all, "questions", jobMatchId] as const,
};
