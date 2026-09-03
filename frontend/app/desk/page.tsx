"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { SystemHealthPanel } from "@/features/admin";
import { useAuth } from "@/providers/auth-provider";
import { getUserHome } from "@/src/lib/product-doors";

export default function DeskIndexPage() {
  const router = useRouter();
  const { user } = useAuth();
  const isOwner =
    !!user && (user.is_superuser || user.role_name === "admin" || user.role_name === "team_owner");

  useEffect(() => {
    if (user && !isOwner) {
      router.replace(getUserHome(user));
    }
  }, [isOwner, router, user]);

  if (!isOwner) {
    return null;
  }

  return <SystemHealthPanel />;
}
