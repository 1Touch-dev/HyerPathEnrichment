import { QueueMonitor } from "@/features/admin";

export default function AdminQueuesPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Queues</h1>
      <QueueMonitor />
    </div>
  );
}
