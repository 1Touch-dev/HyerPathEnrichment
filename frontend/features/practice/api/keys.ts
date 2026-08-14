export const practiceKeys = {
  all: ["practice"] as const,
  sessions: () => [...practiceKeys.all, "sessions"] as const,
  session: (id: string) => [...practiceKeys.all, "session", id] as const,
  audioStatus: (id: string) => [...practiceKeys.all, "audio-status", id] as const,
};
