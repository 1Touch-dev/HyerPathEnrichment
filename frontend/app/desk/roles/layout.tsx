"use client";

import { AdminGuard } from "@/components/auth/admin-guard";

export default function RolesLayout({ children }: { children: React.ReactNode }) {
  return <AdminGuard permission={{ resource: "roles", action: "read" }}>{children}</AdminGuard>;
}
