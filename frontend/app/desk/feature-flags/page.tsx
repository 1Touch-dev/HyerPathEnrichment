import { DeskPage } from "@/components/desk/desk-shell";
import { FeatureFlagsPanel } from "@/features/admin";

export default function AdminFeatureFlagsPage() {
  return (
    <DeskPage
      eyebrow="Desk administration"
      title="Feature flags"
      description="Inspect stored flag records and their provenance while keeping this surface explicitly read-only until a real application consumer exists."
    >
      <FeatureFlagsPanel />
    </DeskPage>
  );
}
