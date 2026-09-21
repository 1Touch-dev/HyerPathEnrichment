import { DeskPage } from "@/components/desk/desk-shell";
import { SourcingLeadsPanel } from "@/features/admin/components/SourcingLeadsPanel";

export default function AdminSourcingLeadsPage() {
  return (
    <DeskPage
      eyebrow="Desk execution"
      title="LinkedIn sourcing leads"
      description="Capture manually observed candidate leads and review them in queue form without introducing any LinkedIn automation or autofill behavior."
    >
      <SourcingLeadsPanel />
    </DeskPage>
  );
}
