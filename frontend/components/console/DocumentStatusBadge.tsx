import { Clock, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/src/lib/utils";

type DocumentProcessingStatus = "pending" | "processing" | "completed" | "failed" | "duplicate";

const variantMap: Record<
  DocumentProcessingStatus,
  "secondary" | "warning" | "success" | "destructive" | "outline"
> = {
  pending: "secondary",
  processing: "warning",
  completed: "success",
  failed: "destructive",
  duplicate: "outline",
};

function isKnownStatus(status: string): status is DocumentProcessingStatus {
  return status in variantMap;
}

export function DocumentStatusBadge({ status }: { status: string }) {
  const isAnimated = status === "processing" || status === "pending";
  const variant = isKnownStatus(status) ? variantMap[status] : "outline";

  return (
    <Badge variant={variant} className={cn(isAnimated && "animate-pulse")}>
      {status === "pending" && <Clock className="mr-1 size-3" />}
      {status === "processing" && <Loader2 className="mr-1 size-3 animate-spin" />}
      {status}
    </Badge>
  );
}
