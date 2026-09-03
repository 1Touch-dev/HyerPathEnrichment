"use client";

import { AppShell } from "@/components/layout/AppShell";
import { AuthGuard } from "@/components/auth/auth-guard";
import { AdminGuard } from "@/components/auth/admin-guard";

/**
 * Desk shell (CTR-GUARD / DEC-04). AuthGuard is the door until Dev A
 * StaffGuard + AppShell product="desk". AdminGuard is the owner-only gate.
 *
 * SEC-000: do not render children without AuthGuard. Anonymous users must hit
 * login. Candidates must not remain on /desk. Recruiter on /desk/roles must bounce.
 */
export default function DeskLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>
        <AdminGuard>{children}</AdminGuard>
      </AppShell>
    </AuthGuard>
  );
}
