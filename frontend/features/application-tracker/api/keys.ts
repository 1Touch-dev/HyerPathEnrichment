import type { ApplicationStatus } from "@/src/lib/types";

export const applicationTrackerKeys = {
  all: ["application-tracker"] as const,
  matches: (status: ApplicationStatus | undefined, sort: string, limit: number, offset: number) =>
    [...applicationTrackerKeys.all, "matches", status ?? "all", sort, limit, offset] as const,
};
