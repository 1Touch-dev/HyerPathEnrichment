import { DsarOpsForm } from '@/features/compliance';

export default function PrivacyPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Privacy &amp; DSAR</h1>
        <p className="text-sm text-muted-foreground">Internal data subject access request operations.</p>
      </div>
      <DsarOpsForm />
    </div>
  );
}
