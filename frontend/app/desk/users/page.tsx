import { UsersTable } from "@/features/admin";

export default function AdminUsersPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
      <UsersTable />
    </div>
  );
}
