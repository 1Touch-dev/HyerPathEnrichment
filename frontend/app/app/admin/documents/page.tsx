import { DocumentsModerationPanel } from "@/features/admin/components/DocumentsModerationPanel";

export default function AdminDocumentsPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
      <DocumentsModerationPanel />
    </div>
  );
}
