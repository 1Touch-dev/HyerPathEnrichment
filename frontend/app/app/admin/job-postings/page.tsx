import { JobPostingsModerationPanel } from "@/features/admin";

export default function AdminJobPostingsPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Job Postings</h1>
      <JobPostingsModerationPanel />
    </div>
  );
}
