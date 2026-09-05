import { DemandIntelligencePanel } from "@/features/demand-intelligence/components/DemandIntelligencePanel";

export default function AdminDemandIntelligencePage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Demand Intelligence</h1>
      <DemandIntelligencePanel />
    </div>
  );
}
