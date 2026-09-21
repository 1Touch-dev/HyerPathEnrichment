import { DeskPage } from "@/components/desk/desk-shell";
import { SystemHealthPanel } from "@/features/admin";

export default function AdminSystemHealthPage() {
  return (
    <DeskPage
      eyebrow="Desk observability"
      title="System health"
      description="Watch service readiness, datastore latency, and golden-signal availability with the same fallbacks and permissions already in place."
    >
      <SystemHealthPanel />
    </DeskPage>
  );
}
