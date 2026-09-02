"use client";

import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { isStaffUser } from "@/src/lib/product-doors";

export function StaffGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const { user, loading } = useAuth();
  const isStaff = isStaffUser(user);

  useEffect(() => {
    if (!loading && !user) {
      const destination = search ? `${pathname}?${search}` : pathname;
      router.replace(`/login?redirect=${encodeURIComponent(destination)}`);
      return;
    }
    if (!loading && user && !isStaff) {
      router.replace("/app/matches");
    }
  }, [isStaff, loading, pathname, router, search, user]);

  if (loading || !user || !isStaff) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return <>{children}</>;
}
