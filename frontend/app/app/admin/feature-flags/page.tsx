import { FeatureFlagsPanel } from "@/features/admin";

export default function AdminFeatureFlagsPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Feature flags</h1>
      <FeatureFlagsPanel />
    </div>
  );
}
