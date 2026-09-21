import { DeskPage } from "@/components/desk/desk-shell";
import { DocumentsModerationPanel } from "@/features/admin";

export default function AdminDocumentsPage() {
  return (
    <DeskPage
      eyebrow="Desk moderation"
      title="Documents"
      description="Review document processing posture and soft-delete controls while preserving restore behavior, filters, and cursor pagination."
    >
      <DocumentsModerationPanel />
    </DeskPage>
  );
}
