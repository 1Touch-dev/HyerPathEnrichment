import { Dossier } from "@/src/lib/types";
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

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-4">
        <PhotoCard photo={dossier.photo || null} fallbackText={title} size="lg" />
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
          <p className="text-sm text-muted-foreground">
            {dossier.handles.length} handles · {dossier.emails.length} emails
            {dossier.confidence.length > 0 && " · top confidence "}
            {dossier.confidence.length > 0 && (loading ? "…" : formatPercent(topConfidence))}
          </p>
        </div>
      </div>

      {/* Overall Confidence Meter */}
      {topConfidence > 0 && (
        <div className="flex flex-col items-center sm:items-end">
          <div className="w-20 h-20 mb-1">
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
          <p className="text-xs text-muted-foreground">Top Confidence</p>
        </div>
      )}
    </div>
  );
}
