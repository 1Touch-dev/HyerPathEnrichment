import { useQuery } from "@tanstack/react-query";
import { fetchAuditLogs } from "../api/client";
import { adminKeys } from "../api/keys";

export function useAuditLogs(cursor: string | null, action: string | null = null) {
  return useQuery({
    queryKey: adminKeys.auditLogs(cursor, action),
    queryFn: () => fetchAuditLogs(cursor, action),
  });
}
