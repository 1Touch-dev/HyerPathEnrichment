"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { RouteGuardStatus } from "./route-guard-status";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      const destination = `${pathname}${window.location.search}`;
      router.push(`/login?redirect=${encodeURIComponent(destination)}`);
    }
  }, [loading, user, router, pathname]);

  if (loading) {
    return <RouteGuardStatus message="Loading account" />;
  }

  if (!user) {
    return <RouteGuardStatus message="Redirecting to login" />;
  }

  return <>{children}</>;
}
