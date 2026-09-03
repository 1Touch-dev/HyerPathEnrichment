"use client";

import { useRouter, useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/console/EmptyState";
import { UserDetailDrawer, useAdminUsers } from "@/features/admin";

/**
 * Deep-linkable full-page rendering of UserDetailDrawer. There is no
 * `GET /api/admin/users/{id}` endpoint (the backend only exposes cursor-paginated
 * list + status/role mutations, §12.7) — so, consistent with AuditLogTable's own
 * "resolved client-side from a small useAdminUsers-backed lookup, or left
 * unresolved" pattern (§12.4), this resolves the user from the first cursor
 * page and shows a graceful fallback if a deep link lands on a user further
 * back in a large user list.
 */
export default function AdminUserDetailPage() {
  const router = useRouter();
  const params = useParams<{ userId: string }>();
  const userId = params.userId;

  const { data, isLoading } = useAdminUsers(null, null);
  const targetUser = data?.items.find((item) => item.id === userId);

  function goBack() {
    router.push("/desk/users");
  }

  if (isLoading && !data) {
    return <p className="text-sm text-muted-foreground">Loading user…</p>;
  }

  if (!targetUser) {
    return (
      <div className="flex flex-col gap-4">
        <Button variant="ghost" onClick={goBack} className="w-fit">
          <ArrowLeft className="mr-2 size-4" />
          Back to Users
        </Button>
        <EmptyState
          title="User not found on this page"
          description="This user isn't on the most recently loaded page of results. Use the Users list to search for them."
        />
      </div>
    );
  }

  return (
    <UserDetailDrawer
      user={targetUser}
      open
      onOpenChange={(open) => {
        if (!open) goBack();
      }}
    />
  );
}
