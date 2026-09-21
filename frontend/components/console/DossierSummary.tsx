import { Dossier } from "@/src/lib/types";
import { Badge } from "@/components/ui/badge";
import { getTierLabel } from "@/src/lib/tier-utils";
import { formatPercent } from "@/src/lib/utils";
import { PhotoCard } from "@/components/dossier/PhotoCard";
import { CircularProgressbar, buildStyles } from "react-circular-progressbar";
import "react-circular-progressbar/dist/styles.css";

type DossierSummaryProps = {
  dossier: Dossier;
  loading?: boolean;
};

function getProgressColor(score: number): string {
  if (score >= 0.9) return "#10b981"; // green-500
  if (score >= 0.7) return "#f59e0b"; // amber-500
  return "#f97316"; // orange-500
}

export function DossierSummary({ dossier, loading }: DossierSummaryProps) {
  const title = dossier.metadata.identifierSummary || "Enrichment result";
  const topConfidence = dossier.confidence[0]?.score ?? dossier.photo?.confidence ?? 0;
  const evidenceCount =
    dossier.handles.length +
    dossier.emails.length +
    dossier.verifiedEmails.length +
    dossier.jobs.length;

  return (
    <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-center">
        <PhotoCard photo={dossier.photo || null} fallbackText={title} size="lg" />
        <div className="min-w-0 space-y-3">
          <div>
            <h2 className="truncate text-2xl font-semibold tracking-tight">{title}</h2>
            <p className="text-sm text-muted-foreground">
              {evidenceCount} evidence point{evidenceCount === 1 ? "" : "s"} surfaced across the
              requested tiers.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{dossier.handles.length} handles</Badge>
            <Badge variant="outline">
              {dossier.emails.length + dossier.verifiedEmails.length} emails
            </Badge>
            <Badge variant="outline">{dossier.jobs.length} professional leads</Badge>
            <Badge variant="outline">{dossier.sources.length} sources</Badge>
            {dossier.metadata.requestedTiers.map((tier) => (
              <Badge key={tier} variant="secondary">
                {getTierLabel(tier)}
              </Badge>
            ))}
          </div>
        </div>
      </div>

      {topConfidence > 0 && (
        <div className="flex flex-col items-center sm:items-end">
          <div className="mb-1 h-20 w-20">
            <CircularProgressbar
              value={topConfidence * 100}
              text={`${Math.round(topConfidence * 100)}%`}
              styles={buildStyles({
                textSize: "20px",
                pathColor: getProgressColor(topConfidence),
                textColor: "currentColor",
                trailColor: "rgba(0, 0, 0, 0.1)",
              })}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Top confidence {loading ? "updating…" : formatPercent(topConfidence)}
          </p>
        </div>
      )}
    </div>
  );
}
