"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { RouteGuardStatus } from "@/components/auth/route-guard-status";
import { SystemHealthPanel } from "@/features/admin";
import { useAuth } from "@/providers/auth-provider";
import { canAccessDeskHome, getUserHome } from "@/src/lib/product-doors";

export default function DeskIndexPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const canAccess = canAccessDeskHome(user);

  useEffect(() => {
    if (!loading && user && !canAccess) {
      router.replace(getUserHome(user));
    }
  }, [canAccess, loading, router, user]);

  if (loading) {
    return <RouteGuardStatus message="Loading account" />;
  }

  if (!user || !canAccess) {
    return <RouteGuardStatus message="You don't have access to this page" />;
  }

  return <SystemHealthPanel />;
}
