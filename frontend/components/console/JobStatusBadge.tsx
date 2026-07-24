import { Clock, Loader2 } from "lucide-react";
import { JobStatus } from "@/src/lib/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/src/lib/utils";

const variantMap: Record<
  JobStatus,
  "secondary" | "warning" | "success" | "destructive" | "outline"
> = {
  queued: "secondary",
  running: "warning",
  completed: "success",
  completed_no_data: "outline",
  failed: "destructive",
  suppressed: "outline",
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const isAnimated = status === "running" || status === "queued";

  return (
    <Badge variant={variantMap[status]} className={cn(isAnimated && "animate-pulse")}>
      {status === "queued" && <Clock className="mr-1 size-3" />}
      {status === "running" && <Loader2 className="mr-1 size-3 animate-spin" />}
      {status}
    </Badge>
  );
}
