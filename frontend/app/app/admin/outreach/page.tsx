import { OutreachModerationPanel } from "@/features/admin/components/OutreachModerationPanel";

export default function AdminOutreachPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Outreach moderation</h1>
      <OutreachModerationPanel />
    </div>
  );
}
