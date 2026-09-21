import { DeskPage } from "@/components/desk/desk-shell";
import { AiActionsTable } from "@/features/admin";

export default function AdminAiActionsPage() {
  return (
    <DeskPage
      eyebrow="Desk observability"
      title="AI actions"
      description="Oversight view for generated actions, drill-down detail, and operator filters without changing action audit semantics or pagination."
    >
      <AiActionsTable />
    </DeskPage>
  );
}
