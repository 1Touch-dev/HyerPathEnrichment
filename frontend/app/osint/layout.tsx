"use client";

import { StaffGuard } from "@/components/auth/staff-guard";
import { AppShell } from "@/components/layout/AppShell";

export default function OsintLayout({ children }: { children: React.ReactNode }) {
  return (
    <StaffGuard>
      <AppShell product="osint">{children}</AppShell>
    </StaffGuard>
  );
}
