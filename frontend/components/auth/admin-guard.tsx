"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessDeskHome,
  getUserHome,
  hasPermission,
  type Permission,
} from "@/src/lib/product-doors";
import { RouteGuardStatus } from "./route-guard-status";
import { redirectAfterDomContentLoaded } from "./route-guard-utils";

type AdminGuardProps = {
  children: React.ReactNode;
  permission?: Permission;
};

export function AdminGuard({ children, permission }: AdminGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const canAccess = permission ? hasPermission(user, permission) : canAccessDeskHome(user);

  useEffect(() => {
    if (!loading && !user) {
      const destination = `${pathname}${window.location.search}`;
      router.replace(`/login?redirect=${encodeURIComponent(destination)}`);
      return;
    }
    if (!loading && user && !canAccess) {
      return redirectAfterDomContentLoaded(() => router.replace(getUserHome(user)));
    }
  }, [canAccess, loading, pathname, router, user]);

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
