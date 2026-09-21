import { DeskPage } from "@/components/desk/desk-shell";
import { JobPostingsModerationPanel } from "@/features/admin";

export default function AdminJobPostingsPage() {
  return (
    <DeskPage
      eyebrow="Desk moderation"
      title="Job postings"
      description="Moderate listing visibility and removals with the same status transitions, reasons, and audit capture already defined in the admin API."
    >
      <JobPostingsModerationPanel />
    </DeskPage>
  );
}
