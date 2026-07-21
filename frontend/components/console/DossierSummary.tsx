import Image from "next/image";
import { Dossier } from "@/src/lib/types";
import { formatPercent, initialsFrom } from "@/src/lib/utils";

type DossierSummaryProps = {
  dossier: Dossier;
  loading?: boolean;
};

export function DossierSummary({ dossier, loading }: DossierSummaryProps) {
  const title = dossier.metadata.identifierSummary || "Enrichment result";
  const topConfidence = dossier.confidence[0]?.score ?? dossier.photo?.confidence ?? 0;

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-4">
        {dossier.photo?.assetUrl ? (
          <Image
            src={dossier.photo.assetUrl}
            alt={title}
            width={56}
            height={56}
            unoptimized
            className="size-14 rounded-full object-cover"
          />
        ) : (
          <div className="flex size-14 items-center justify-center rounded-full bg-muted text-sm font-semibold">
            {initialsFrom(title)}
          </div>
        )}
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
          <p className="text-sm text-muted-foreground">
            {dossier.handles.length} handles · {dossier.emails.length} emails · top confidence{" "}
            {loading ? "…" : formatPercent(topConfidence)}
          </p>
        </div>
      </div>
    </div>
  );
}
