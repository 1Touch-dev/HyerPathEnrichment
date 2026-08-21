import { Badge } from "@/components/ui/badge";

type RoleBadgeProps = {
  isSuperuser: boolean;
  roleName: string | null;
};

/**
 * Maps a user's `isSuperuser`/`roleName` fields to a colored Badge — superuser
 * is the direct-column override gate (Decision 1), so it always wins over
 * whatever `roleName` also happens to be set.
 */
export function RoleBadge({ isSuperuser, roleName }: RoleBadgeProps) {
  if (isSuperuser) {
    return <Badge variant="destructive">Superuser</Badge>;
  }
  if (roleName === "admin") {
    return <Badge variant="default">Admin</Badge>;
  }
  if (roleName === "support") {
    return <Badge variant="secondary">Support</Badge>;
  }
  return <Badge variant="outline">No role</Badge>;
}
