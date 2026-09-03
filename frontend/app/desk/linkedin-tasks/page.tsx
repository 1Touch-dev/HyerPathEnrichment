import { LinkedInTasksPanel } from "@/features/admin";

export default function AdminLinkedInTasksPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">LinkedIn send tasks</h1>
      <LinkedInTasksPanel />
    </div>
  );
}
