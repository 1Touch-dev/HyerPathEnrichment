"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { SystemHealthPanel } from "@/features/admin";
import { useAuth } from "@/providers/auth-provider";
import { getUserHome, isOwnerUser } from "@/src/lib/product-doors";

export default function DeskIndexPage() {
  const router = useRouter();
  const { user } = useAuth();
  const isOwner = isOwnerUser(user);

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
