import { DeskPage } from "@/components/desk/desk-shell";
import { AnalyticsPanel } from "@/features/admin";

export default function AdminAnalyticsPage() {
  return (
    <DeskPage
      eyebrow="Desk observability"
      title="Analytics"
      description="Monitor aggregate job-match activity, cache posture, and source mix without changing the underlying BFF analytics contract."
    >
      <AnalyticsPanel />
    </DeskPage>
  );
}
