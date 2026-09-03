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

export function getUserHome(user: ProductDoorUser): string {
  if (!isStaffUser(user)) {
    return "/app/matches";
  }
  if (user.is_superuser || user.role_name === "admin" || user.role_name === "team_owner") {
    return "/desk";
  }
  if (user.role_name === "recruiter") {
    return "/desk/sourcing-leads";
  }
  if (user.role_name === "support") {
    return "/desk/users";
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
