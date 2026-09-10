import { DeskPage } from "@/components/desk/desk-shell";
import { PortfolioModerationPanel } from "@/features/admin";

export default function AdminPortfolioPage() {
  return (
    <DeskPage
      eyebrow="Desk moderation"
      title="Portfolio moderation"
      description="Control published portfolio visibility with the existing moderation mutations and keep review actions dense, explicit, and reversible."
    >
      <PortfolioModerationPanel />
    </DeskPage>
  );
}
