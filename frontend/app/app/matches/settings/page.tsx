import { PreferencesForm } from "@/features/job-matching";

export default function MatchPreferencesPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6 py-8">
      <div>
        <h1 className="text-2xl font-semibold">Job match preferences</h1>
        <p className="text-muted-foreground">
          Tell us what you're looking for and we'll scan job boards daily.
        </p>
      </div>
      <PreferencesForm />
    </div>
  );
}
