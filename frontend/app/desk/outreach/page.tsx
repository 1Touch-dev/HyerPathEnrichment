import { DeskPage } from "@/components/desk/desk-shell";
import { OutreachModerationPanel } from "@/features/admin";

export default function AdminOutreachPage() {
  return (
    <DeskPage
      eyebrow="Desk moderation"
      title="Outreach moderation"
      description="Review message status and block posture with the same moderation rules while presenting the queue in a denser operator workflow."
    >
      <OutreachModerationPanel />
    </DeskPage>
  );
}
