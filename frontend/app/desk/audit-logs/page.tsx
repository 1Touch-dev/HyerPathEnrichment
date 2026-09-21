import { DeskPage } from "@/components/desk/desk-shell";
import { AuditLogTable } from "@/features/admin";

export default function AdminAuditLogsPage() {
  return (
    <DeskPage
      eyebrow="Desk observability"
      title="Audit logs"
      description="Trace admin-side changes with action filters and cursor pagination while preserving the current audit vocabulary and actor resolution behavior."
    >
      <AuditLogTable />
    </DeskPage>
  );
}
