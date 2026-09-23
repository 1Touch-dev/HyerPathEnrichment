import { MarketingShell } from "@/components/layout/MarketingShell";
import { OptOutForm } from "@/components/opt-out/OptOutForm";
import { Card, CardContent } from "@/components/ui/card";

const HOW_IT_WORKS = [
  {
    step: "01",
    title: "Submit an identifier",
    body: "Email, LinkedIn URL, or username — the same forms used for enrichment.",
  },
  {
    step: "02",
    title: "Hashed and suppressed",
    body: "We store a SHA-256 hash on the suppression list. Raw identifiers are not retained for marketing.",
  },
  {
    step: "03",
    title: "Data purged",
    body: "Matching jobs, photo cache, and stored assets are erased. Future enrichment returns an empty dossier.",
  },
] as const;

export default function OptOutPage() {
  return (
    <MarketingShell>
      <div className="mx-auto flex max-w-xl flex-col gap-10 px-4 py-12 sm:py-16">
        <section className="flex flex-col gap-4 rounded-[1.5rem] border border-border/70 bg-surface p-6 text-center shadow-panel sm:p-10">
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-primary">
            Privacy
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Opt out of enrichment
          </h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Public data-subject request form. No console login required. We process opt-out, access,
            and deletion requests under LGPD / GDPR / CCPA.
          </p>
        </section>

        <OptOutForm />

        <section className="flex flex-col gap-4" aria-labelledby="how-it-works">
          <h2 id="how-it-works" className="text-center text-lg font-semibold tracking-tight">
            How it works
          </h2>
          <ol className="flex flex-col gap-3">
            {HOW_IT_WORKS.map((item) => (
              <li key={item.step}>
                <Card variant="accent" className="border-border/70">
                  <CardContent className="p-4">
                    <p className="font-mono text-xs text-primary">{item.step}</p>
                    <p className="mt-1 text-sm font-medium">{item.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{item.body}</p>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </MarketingShell>
  );
}
