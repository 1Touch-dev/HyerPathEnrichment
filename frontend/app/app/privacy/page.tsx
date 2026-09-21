import {
  ShellPageHeader,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
  ShellSection,
} from "@/components/layout/ShellPage";
import { DsarOpsForm } from "@/features/compliance";

export default function PrivacyPage() {
  return (
    <div className="flex flex-col gap-6">
      <ShellPageHeader>
        <ShellPageHeaderContent>
          <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
          <ShellPageHeaderTitle>Privacy requests</ShellPageHeaderTitle>
          <ShellPageHeaderDescription>
            Ask for a copy of your data or request deletion from one place. Public opt-out is still
            available on the marketing site.
          </ShellPageHeaderDescription>
        </ShellPageHeaderContent>
      </ShellPageHeader>
      <ShellSection className="max-w-4xl">
        <DsarOpsForm />
      </ShellSection>
    </div>
  );
}
