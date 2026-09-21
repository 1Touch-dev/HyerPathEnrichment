import {
  ShellPageHeader,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
  ShellSection,
} from "@/components/layout/ShellPage";
import { PreferencesForm } from "@/features/job-matching";

export default function MatchPreferencesPage() {
  return (
    <div className="space-y-6">
      <ShellPageHeader>
        <ShellPageHeaderContent>
          <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
          <ShellPageHeaderTitle>Job match preferences</ShellPageHeaderTitle>
          <ShellPageHeaderDescription>
            Tell us what you want to see more of, where you want to hear about it, and how active
            daily scans should be.
          </ShellPageHeaderDescription>
        </ShellPageHeaderContent>
      </ShellPageHeader>
      <ShellSection className="mx-auto w-full max-w-4xl">
        <PreferencesForm />
      </ShellSection>
    </div>
  );
}
