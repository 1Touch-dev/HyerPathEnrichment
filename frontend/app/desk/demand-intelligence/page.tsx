import { DeskPage } from "@/components/desk/desk-shell";
import { DemandIntelligencePanel } from "@/features/demand-intelligence/components/DemandIntelligencePanel";

export default function AdminDemandIntelligencePage() {
  return (
    <DeskPage
      eyebrow="Desk intelligence"
      title="Demand intelligence"
      description="Search role-level country demand and sourcing priority without altering the existing query flow or backend aggregation behavior."
    >
      <DemandIntelligencePanel />
    </DeskPage>
  );
}
