"use client";

import { AppShell } from "@/components/layout/AppShell";
import { AuthGuard } from "@/components/auth/auth-guard";

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  );
}
