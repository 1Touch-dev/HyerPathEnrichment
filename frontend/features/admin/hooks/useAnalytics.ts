import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJobMatchAnalytics } from "../api/client";
import { adminKeys } from "../api/keys";

export function useJobMatchAnalytics() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: adminKeys.analytics(),
    queryFn: () => fetchJobMatchAnalytics(false),
  });
  const refresh = async () => {
    const data = await fetchJobMatchAnalytics(true);
    queryClient.setQueryData(adminKeys.analytics(), data);
  };
  return { ...query, refresh };
}
