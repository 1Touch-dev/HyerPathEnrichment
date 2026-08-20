import { ReviewQueueTable } from "@/features/admin/components/ReviewQueueTable";

export default function AdminReviewQueuePage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Review queue</h1>
      <ReviewQueueTable />
    </div>
  );
}
