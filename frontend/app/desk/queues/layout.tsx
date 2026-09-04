"use client";

import { AdminGuard } from "@/components/auth/admin-guard";

export default function QueuesLayout({ children }: { children: React.ReactNode }) {
  return <AdminGuard permission={{ resource: "queues", action: "read" }}>{children}</AdminGuard>;
}
