"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import {
  getRequiredDeskPermission,
  getUserHome,
  hasPermission,
  isStaffUser,
} from "@/src/lib/product-doors";
import { RouteGuardStatus } from "./route-guard-status";
import { redirectAfterDomContentLoaded } from "./route-guard-utils";

export function StaffGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const isStaff = isStaffUser(user);
  const requiredPermission = pathname.startsWith("/desk")
    ? getRequiredDeskPermission(pathname)
    : null;
  const canAccess = isStaff && (!requiredPermission || hasPermission(user, requiredPermission));

  useEffect(() => {
    if (!loading && !user) {
      const destination = `${pathname}${window.location.search}`;
      router.replace(`/login?redirect=${encodeURIComponent(destination)}`);
      return;
    }
    if (!loading && user && !canAccess) {
      const destination = isStaff ? getUserHome(user) : "/app/matches";
      return redirectAfterDomContentLoaded(() => router.replace(destination));
    }
  }, [canAccess, isStaff, loading, pathname, router, user]);

  if (loading || !user || !canAccess) {
    const message = loading
      ? "Loading account"
      : !user
        ? "Redirecting to login"
        : "You don't have access to this page";
    return <RouteGuardStatus message={message} />;
  }

  return <>{children}</>;
}
