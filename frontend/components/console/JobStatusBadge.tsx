import { JobStatus } from "@/src/lib/types";
import { Badge } from "@/components/ui/badge";

const variantMap: Record<
  JobStatus,
  "secondary" | "warning" | "success" | "destructive" | "outline"
> = {
  queued: "secondary",
  running: "warning",
  completed: "success",
  failed: "destructive",
  suppressed: "outline",
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return <Badge variant={variantMap[status]}>{status}</Badge>;
}
