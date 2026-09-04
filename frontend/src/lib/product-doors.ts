export type Product = "candidate" | "desk" | "osint";

export type Permission = {
  resource: string;
  action: string;
};

export type ProductDoorUser = {
  is_superuser: boolean;
  role_id?: string | null;
  role_name?: string | null;
  permissions?: Permission[];
};

export const PRODUCT_ROOTS: Record<Product, string> = {
  candidate: "/app",
  desk: "/desk",
  osint: "/osint",
};

export function isStaffUser(user: ProductDoorUser | null | undefined): boolean {
  return !!user && (user.is_superuser || user.role_id != null);
}

export const DESK_HOME_PERMISSION: Permission = {
  resource: "system_health",
  action: "read",
};

const DESK_HOME_FALLBACKS: ReadonlyArray<{ href: string; permission: Permission }> = [
  { href: "/desk", permission: DESK_HOME_PERMISSION },
  { href: "/desk/sourcing-leads", permission: { resource: "linkedin_sourcing", action: "write" } },
  { href: "/desk/users", permission: { resource: "users", action: "read" } },
  { href: "/desk/brands", permission: { resource: "brands", action: "read" } },
  { href: "/desk/roles", permission: { resource: "roles", action: "read" } },
  { href: "/desk/feature-flags", permission: { resource: "feature_flags", action: "read" } },
  { href: "/desk/queues", permission: { resource: "queues", action: "read" } },
  { href: "/desk/audit-logs", permission: { resource: "audit_logs", action: "read" } },
  { href: "/desk/review-queue", permission: { resource: "content_review", action: "read" } },
  { href: "/desk/job-postings", permission: { resource: "job_postings", action: "read" } },
  { href: "/desk/documents", permission: { resource: "documents", action: "read" } },
  { href: "/desk/portfolio", permission: { resource: "portfolio", action: "read" } },
  { href: "/desk/outreach", permission: { resource: "outreach", action: "read" } },
  { href: "/desk/linkedin-tasks", permission: { resource: "linkedin_tasks", action: "operate" } },
  { href: "/desk/analytics", permission: { resource: "analytics", action: "read" } },
  { href: "/desk/ai-actions", permission: { resource: "ai_supervision", action: "read" } },
  { href: "/desk/demand-intelligence", permission: { resource: "analytics", action: "read" } },
  { href: "/desk/signals", permission: { resource: "system_health", action: "read" } },
];

const DESK_ROUTE_PERMISSIONS: ReadonlyArray<{ prefix: string; permission: Permission }> = [
  {
    prefix: "/desk/sourcing-leads",
    permission: { resource: "linkedin_sourcing", action: "write" },
  },
  { prefix: "/desk/brands", permission: { resource: "brands", action: "read" } },
  { prefix: "/desk/users", permission: { resource: "users", action: "read" } },
  { prefix: "/desk/system-health", permission: { resource: "system_health", action: "read" } },
  { prefix: "/desk/roles", permission: { resource: "roles", action: "read" } },
  { prefix: "/desk/staff-invites", permission: { resource: "users", action: "write" } },
  { prefix: "/desk/audit-logs", permission: { resource: "audit_logs", action: "read" } },
  { prefix: "/desk/feature-flags", permission: { resource: "feature_flags", action: "read" } },
  { prefix: "/desk/queues", permission: { resource: "queues", action: "read" } },
  { prefix: "/desk/analytics", permission: { resource: "analytics", action: "read" } },
  { prefix: "/desk/review-queue", permission: { resource: "content_review", action: "read" } },
  { prefix: "/desk/job-postings", permission: { resource: "job_postings", action: "read" } },
  { prefix: "/desk/documents", permission: { resource: "documents", action: "read" } },
  { prefix: "/desk/portfolio", permission: { resource: "portfolio", action: "read" } },
  { prefix: "/desk/outreach", permission: { resource: "outreach", action: "read" } },
  { prefix: "/desk/linkedin-tasks", permission: { resource: "linkedin_tasks", action: "operate" } },
  { prefix: "/desk/ai-actions", permission: { resource: "ai_supervision", action: "read" } },
  { prefix: "/desk/demand-intelligence", permission: { resource: "analytics", action: "read" } },
  { prefix: "/desk/signals", permission: { resource: "system_health", action: "read" } },
];

export function getUserHome(user: ProductDoorUser): string {
  if (!isStaffUser(user)) {
    return "/app/matches";
  }
  for (const candidate of DESK_HOME_FALLBACKS) {
    if (hasPermission(user, candidate.permission)) {
      return candidate.href;
    }
  }
  return "/osint";
}

export function getDefaultProduct(user: ProductDoorUser): Product {
  const home = getUserHome(user);
  if (home.startsWith(PRODUCT_ROOTS.desk)) {
    return "desk";
  }
  if (home.startsWith(PRODUCT_ROOTS.osint)) {
    return "osint";
  }
  return "candidate";
}

export function hasPermission(
  user: ProductDoorUser | null | undefined,
  permission: Permission,
): boolean {
  return (
    !!user &&
    (user.is_superuser ||
      (user.permissions ?? []).some(
        ({ resource, action }) => resource === permission.resource && action === permission.action,
      ))
  );
}

export function canAccessDeskHome(user: ProductDoorUser | null | undefined): boolean {
  return hasPermission(user, DESK_HOME_PERMISSION);
}

export function getRequiredDeskPermission(pathname: string): Permission | null {
  let bestMatch: Permission | null = null;
  let bestLength = -1;
  for (const route of DESK_ROUTE_PERMISSIONS) {
    if (pathname === route.prefix || pathname.startsWith(`${route.prefix}/`)) {
      if (route.prefix.length > bestLength) {
        bestLength = route.prefix.length;
        bestMatch = route.permission;
      }
    }
  }
  return bestMatch;
}

export function filterByPermissions<T extends { permission?: Permission }>(
  items: readonly T[],
  user: ProductDoorUser | null | undefined,
): T[] {
  return items.filter((item) => !item.permission || hasPermission(user, item.permission));
}

export function safeLocalRedirect(value: string | null | undefined): string | null {
  if (!value?.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return null;
  }

  try {
    const base = "https://hyrepath.local";
    const target = new URL(value, base);
    if (target.origin !== base || target.pathname.startsWith("//")) {
      return null;
    }
    return `${target.pathname}${target.search}${target.hash}`;
  } catch {
    return null;
  }
}
