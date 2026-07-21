import { DsarOpsForm } from "@/features/compliance";

export default function PrivacyPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Privacy requests</h1>
        <p className="text-sm text-muted-foreground">
          Submit access or deletion requests. Public opt-out is available on the marketing site.
        </p>
      </div>
      <DsarOpsForm />
    </div>
  );
}
