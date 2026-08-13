import { Badge } from "@/components/ui/badge";
import type { PublicPortfolioProfile } from "@/src/lib/types";

interface PublicPortfolioPageProps {
  profile: PublicPortfolioProfile;
}

const ITEM_TYPE_LABELS: Record<string, string> = {
  github_repo: "GitHub",
  live_demo: "Live demo",
  case_study: "Case study",
  other_link: "Link",
};

export function PublicPortfolioPage({ profile }: PublicPortfolioPageProps) {
  return (
    <article className="mx-auto max-w-2xl space-y-8 px-4 py-12">
      <header>
        {profile.headline && <h1 className="text-3xl font-bold">{profile.headline}</h1>}
        {profile.summary && <p className="mt-3 text-muted-foreground">{profile.summary}</p>}
      </header>

      {profile.items.length > 0 && (
        <section className="space-y-3">
          {profile.items.map((item) => (
            <a
              key={item.itemId}
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block rounded-lg border p-4 transition hover:border-primary"
            >
              <div className="flex items-center justify-between">
                <h2 className="font-medium">{item.title}</h2>
                <Badge variant="outline">{ITEM_TYPE_LABELS[item.itemType] ?? item.itemType}</Badge>
              </div>
              {item.description && <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>}
            </a>
          ))}
        </section>
      )}
    </article>
  );
}
