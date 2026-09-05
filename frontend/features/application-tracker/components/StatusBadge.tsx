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
const STATUS_COLOR: Record<ApplicationStatus, string> = {
  new: "bg-gray-100 text-gray-800",
  applied: "bg-blue-100 text-blue-800",
  replied: "bg-purple-100 text-purple-800",
  interview: "bg-amber-100 text-amber-800",
  offer: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

interface StatusBadgeProps {
  status: ApplicationStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return <Badge className={STATUS_COLOR[status]}>{STATUS_LABEL[status]}</Badge>;
}
