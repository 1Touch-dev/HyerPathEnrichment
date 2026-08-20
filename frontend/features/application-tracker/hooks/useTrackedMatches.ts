import { useQuery } from "@tanstack/react-query";
import { fetchTrackedMatches } from "../api/client";
import { applicationTrackerKeys } from "../api/keys";
import type { ApplicationStatus } from "@/src/lib/types";

export function useTrackedMatches(
  status: ApplicationStatus | undefined,
  sort: string,
  limit = 20,
  offset = 0,
) {
  return useQuery({
    queryKey: applicationTrackerKeys.matches(status, sort, limit, offset),
    queryFn: () => fetchTrackedMatches(status, sort, limit, offset),
  });
}
