"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { isStaffUser } from "@/src/lib/product-doors";
import { RouteGuardStatus } from "./route-guard-status";
import { redirectAfterDomContentLoaded } from "./route-guard-utils";

export function StaffGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const isStaff = isStaffUser(user);

  useEffect(() => {
    if (!loading && !user) {
      const destination = `${pathname}${window.location.search}`;
      router.replace(`/login?redirect=${encodeURIComponent(destination)}`);
      return;
    }
    if (!loading && user && !isStaff) {
      return redirectAfterDomContentLoaded(() => router.replace("/app/matches"));
    }
  }, [isStaff, loading, pathname, router, user]);

  if (loading || !user || !isStaff) {
    const message = loading
      ? "Loading account"
      : !user
        ? "Redirecting to login"
        : "Redirecting to an authorized page";
    return <RouteGuardStatus message={message} />;
  }

  return <>{children}</>;
}
