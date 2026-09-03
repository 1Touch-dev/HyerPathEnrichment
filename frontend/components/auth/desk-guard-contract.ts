/**
 * Gate A freeze (ARCH-001). SRC-PD-05 / SRC-PD-08 / SRC-DB.
 *
 * CTR-URL: admin pages live at /desk/<same-trailing-path>. Index → /desk/system-health.
 * CTR-REDIR: /app/admin → /desk, /app/admin/:path* → /desk/:path* (no enrich→osint).
 * CTR-GUARD (DEC-04): AuthGuard + pathname-aware AdminGuard until Dev A StaffGuard.
 *   unauth → /login?redirect=; candidate → /app/matches; recruiter on owner URLs →
 *   /desk/sourcing-leads. DEC-03: owner-only via pathname, not extra nested layouts.
 * CTR-PERM (DEC-02 fail-closed): owner pages require is_superuser OR roles:write.
 *   Accept string "roles:write", {resource,action}, or {name}. Missing permissions
 *   does not grant owner (superuser still passes). No tenant context (ADR 0019).
 *
 * SEC-000: /desk must not render staff UI for anonymous or candidate users.
 * Recruiter must not stay on owner-only paths. Impersonation exit stays /desk/users.
 */

export const DESK_CANDIDATE_HOME = "/app/matches";
export const DESK_RECRUITER_HOME = "/desk/sourcing-leads";
export const DESK_OWNER_HOME = "/desk";

export const OWNER_ONLY_PATHS = ["/desk/roles", "/desk/feature-flags", "/desk/queues"] as const;

export type DeskPermissionEntry = string | { resource?: string; action?: string; name?: string };

export function isOwnerOnlyPath(pathname: string): boolean {
  return OWNER_ONLY_PATHS.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function isStaffUser(user: {
  is_superuser: boolean;
  role_id?: string | null;
  role_name?: string | null;
}): boolean {
  return !!(user.is_superuser || user.role_id || user.role_name);
}

export function hasRolesWrite(permissions: DeskPermissionEntry[] | undefined): boolean {
  if (!permissions) return false;
  return permissions.some((entry) => {
    if (typeof entry === "string") return entry === "roles:write";
    if (entry.name === "roles:write") return true;
    return entry.resource === "roles" && entry.action === "write";
  });
}

export function isOwnerUser(user: {
  is_superuser: boolean;
  permissions?: DeskPermissionEntry[];
}): boolean {
  return user.is_superuser || hasRolesWrite(user.permissions);
}
