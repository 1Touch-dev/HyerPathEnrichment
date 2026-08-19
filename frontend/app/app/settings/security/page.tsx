import { MfaSetupCard } from "@/features/admin";

export default function SecuritySettingsPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Security</h1>
      <MfaSetupCard />
    </div>
  );
}
