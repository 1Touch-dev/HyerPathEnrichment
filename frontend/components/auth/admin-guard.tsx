"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { Loader2 } from "lucide-react";

/**
 * Derives admin access from the already-fetched /auth/me response — no
 * dedicated admin-only auth call, per docs/admin-module-research.md §12.8's
 * useUserRole() pattern (adapted: this repo has one AuthProvider, not a
 * separate frontend-admin app, so this is a guard component, not a second app).
 */
export function AdminGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const isAdmin = !!user && (user.is_superuser || !!user.role_name);

  useEffect(() => {
    if (!loading && !user) {
      router.push(`/login?redirect=${encodeURIComponent(pathname)}`);
      return;
    }
    if (!loading && user && !isAdmin) {
      router.push("/app/dashboard");
    }
  }, [loading, user, isAdmin, router, pathname]);

  if (loading || !user || !isAdmin) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return <>{children}</>;
}
