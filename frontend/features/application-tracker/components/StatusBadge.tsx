import { Badge } from "@/components/ui/badge";
import type { ApplicationStatus } from "@/src/lib/types";

const STATUS_LABEL: Record<ApplicationStatus, string> = {
  new: "New",
  applied: "Applied",
  replied: "Replied",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

// Reused by Module D's calendar view and Module E's practice-link card (§7.6) —
// kept in its own file rather than inlined in TrackedMatchRow for that reason.
const STATUS_VARIANT: Record<
  ApplicationStatus,
  "outline" | "info" | "secondary" | "warning" | "success" | "destructive"
> = {
  new: "outline",
  applied: "info",
  replied: "secondary",
  interview: "warning",
  offer: "success",
  rejected: "destructive",
};

interface StatusBadgeProps {
  status: ApplicationStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABEL[status]}</Badge>;
}
