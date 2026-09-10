import { DeskPage } from "@/components/desk/desk-shell";
import { UsersTable } from "@/features/admin";

export default function AdminUsersPage() {
  return (
    <DeskPage
      eyebrow="Desk administration"
      title="Users"
      description="Review active and suspended staff accounts, preserve cursor pagination, and keep impersonation and reactivation behavior unchanged."
    >
      <UsersTable />
    </DeskPage>
  );
}
