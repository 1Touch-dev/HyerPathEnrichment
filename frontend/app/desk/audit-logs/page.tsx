import { AuditLogTable } from "@/features/admin";

export default function AdminAuditLogsPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Audit logs</h1>
      <AuditLogTable />
    </div>
  );
}
