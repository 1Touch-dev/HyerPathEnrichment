import { DeskPage } from "@/components/desk/desk-shell";
import { LinkedInTasksPanel } from "@/features/admin";

export default function AdminLinkedInTasksPage() {
  return (
    <DeskPage
      eyebrow="Desk execution"
      title="LinkedIn send tasks"
      description="Run the human-in-the-loop send queue with manual claim, batch, send, and skip flows while keeping all legal-risk constraints intact."
    >
      <LinkedInTasksPanel />
    </DeskPage>
  );
}
