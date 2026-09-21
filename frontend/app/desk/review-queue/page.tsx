import { DeskPage } from "@/components/desk/desk-shell";
import { ReviewQueueTable } from "@/features/admin";

export default function AdminReviewQueuePage() {
  return (
    <DeskPage
      eyebrow="Desk moderation"
      title="Review queue"
      description="Work flagged content with dense filters, drill-down review, and the same decision semantics already enforced by the backend."
    >
      <ReviewQueueTable />
    </DeskPage>
  );
}
