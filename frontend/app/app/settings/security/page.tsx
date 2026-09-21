import {
  ShellPageHeader,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
  ShellSection,
} from "@/components/layout/ShellPage";
import { MfaSetupCard } from "@/features/admin";

export default function SecuritySettingsPage() {
  return (
    <div className="flex flex-col gap-6">
      <ShellPageHeader>
        <ShellPageHeaderContent>
          <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
          <ShellPageHeaderTitle>Security</ShellPageHeaderTitle>
          <ShellPageHeaderDescription>
            Strengthen your account with multi-factor authentication while keeping the existing auth
            flow unchanged.
          </ShellPageHeaderDescription>
        </ShellPageHeaderContent>
      </ShellPageHeader>
      <ShellSection className="max-w-3xl">
        <MfaSetupCard />
      </ShellSection>
    </div>
  );
}
