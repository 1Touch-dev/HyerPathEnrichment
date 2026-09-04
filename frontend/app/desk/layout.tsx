"use client";

import { StaffGuard } from "@/components/auth/staff-guard";
import { AppShell } from "@/components/layout/AppShell";

export default function DeskLayout({ children }: { children: React.ReactNode }) {
  return (
    <StaffGuard>
      <AppShell product="desk">{children}</AppShell>
    </StaffGuard>
  );
}
