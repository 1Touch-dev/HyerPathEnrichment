"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { Loader2 } from "lucide-react";
import { getUserHome, hasPermission, type Permission } from "@/src/lib/product-doors";

type AdminGuardProps = {
  children: React.ReactNode;
  permission?: Permission;
};

export function AdminGuard({ children, permission }: AdminGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const isOwnerOrAdmin =
    !!user && (user.is_superuser || user.role_name === "admin" || user.role_name === "team_owner");
  const canAccess = permission ? hasPermission(user, permission) : isOwnerOrAdmin;

  useEffect(() => {
    if (!loading && !user) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
      return;
    }
    if (!loading && user && !canAccess) {
      router.replace(getUserHome(user));
    }
  }, [canAccess, loading, pathname, router, user]);

  if (loading || !user || !canAccess) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return <>{children}</>;
}
