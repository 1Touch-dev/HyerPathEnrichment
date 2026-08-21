import { useQuery } from "@tanstack/react-query";
import { fetchSystemHealth } from "../api/client";
import { adminKeys } from "../api/keys";

export function useSystemHealth() {
  return useQuery({
    queryKey: adminKeys.systemHealth(),
    queryFn: fetchSystemHealth,
    refetchInterval: 30_000,
  });
}
