import { SourcingLeadsPanel } from "@/features/admin/components/SourcingLeadsPanel";

export default function AdminSourcingLeadsPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">LinkedIn sourcing leads</h1>
      <SourcingLeadsPanel />
    </div>
  );
}
