"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { Loader2 } from "lucide-react";
import {
  DESK_CANDIDATE_HOME,
  DESK_RECRUITER_HOME,
  isOwnerOnlyPath,
  isOwnerUser,
  isStaffUser,
} from "./desk-guard-contract";

/**
 * Owner-only gate for Desk (DEC-03 pathname-aware). Staff door is AuthGuard in
 * desk/layout until Dev A StaffGuard. Non-staff bounce to candidate home.
 * Recruiter hitting roles / feature-flags / queues bounces to sourcing-leads.
 */
export function AdminGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const ownerOnly = isOwnerOnlyPath(pathname);
  const allowed = !!user && isStaffUser(user) && (!ownerOnly || isOwnerUser(user));

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.push(`/login?redirect=${encodeURIComponent(pathname)}`);
      return;
    }
    if (!isStaffUser(user)) {
      router.push(DESK_CANDIDATE_HOME);
      return;
    }
    if (ownerOnly && !isOwnerUser(user)) {
      router.push(DESK_RECRUITER_HOME);
    }
  }, [loading, user, ownerOnly, router, pathname]);

  if (loading || !user || !allowed) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return <>{children}</>;
}
