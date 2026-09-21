import { DeskPage } from "@/components/desk/desk-shell";
import { QueueMonitor } from "@/features/admin";

export default function AdminQueuesPage() {
  return (
    <DeskPage
      eyebrow="Desk observability"
      title="Queues"
      description="Inspect queue depth, failed jobs, and worker coverage while preserving read-only monitoring and the existing expand-for-failures behavior."
    >
      <QueueMonitor />
    </DeskPage>
  );
}
