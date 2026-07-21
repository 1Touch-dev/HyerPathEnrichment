"use client";

import type { ReactNode } from "react";
import type { Dossier } from "@/src/lib/types";
import { RawJsonPanel } from "@/components/console/RawJsonPanel";
import { formatPercent } from "@/src/lib/utils";
import type { DossierEntity } from "./dossier-entity";

type EntityDetailPanelProps = {
  dossier: Dossier;
  entity: DossierEntity;
};

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <div className="shrink-0 text-xs font-medium uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className="text-sm text-foreground">{value}</div>
    </div>
  );
}

export function EntityDetailPanel({ dossier, entity }: EntityDetailPanelProps) {
  return (
    <div className="rounded-lg border bg-card p-5">
      {entity.kind === "handle" ? (
        <>
          <Field label="Type" value="Handle" />
          <Field label="Platform" value={entity.entity.platform} />
          <Field label="Username" value={entity.entity.username} />
          <Field
            label="Profile"
            value={
              <a
                href={entity.entity.profileUrl}
                target="_blank"
                rel="noreferrer"
                className="text-primary underline"
              >
                {entity.entity.profileUrl}
              </a>
            }
          />
          <Field label="Confidence" value={formatPercent(entity.entity.confidence)} />
          {entity.entity.metadata ? (
            <Field
              label="Metadata"
              value={
                <span className="font-mono text-xs">{JSON.stringify(entity.entity.metadata)}</span>
              }
            />
          ) : null}
        </>
      ) : null}

      {entity.kind === "verifiedEmail" ? (
        <>
          <Field label="Type" value="Verified email" />
          <Field label="Email" value={entity.entity.value} />
          <Field label="Status" value={entity.entity.status} />
          <Field label="Source" value={entity.entity.source} />
          <Field label="Confidence" value={formatPercent(entity.entity.confidence)} />
        </>
      ) : null}

      {entity.kind === "email" ? (
        <>
          <Field label="Type" value="Email" />
          <Field label="Email" value={entity.entity} />
          <Field label="Status" value="Unverified" />
        </>
      ) : null}

      {entity.kind === "job" ? (
        <>
          <Field label="Type" value="Job & business" />
          <Field label="Title" value={entity.entity.title} />
          <Field label="Company" value={entity.entity.company} />
          <Field
            label="Location"
            value={`${entity.entity.location} · ${entity.entity.remote ? "Remote" : "On-site"}`}
          />
          <Field label="Source" value={entity.entity.source} />
        </>
      ) : null}

      {entity.kind === "confidence" ? (
        <>
          <Field label="Type" value="Confidence rule" />
          <Field label="Label" value={entity.entity.label} />
          <Field label="Score" value={formatPercent(entity.entity.score)} />
          <Field
            label="Evidence"
            value={<span className="font-mono text-xs">{entity.entity.evidence.join(" · ")}</span>}
          />
        </>
      ) : null}

      {entity.kind === "source" ? (
        <>
          <Field label="Type" value="Source" />
          <Field label="Name" value={<span className="font-mono text-xs">{entity.entity}</span>} />
        </>
      ) : null}

      <div className="mt-4 flex flex-col gap-3 pt-4 border-t border-border">
        <div className="text-sm font-semibold">Job sources</div>
        {dossier.sources.length ? (
          <div className="flex flex-wrap gap-2">
            {dossier.sources.map((s) => (
              <span
                key={s}
                className="rounded-md border border-border bg-muted/30 px-2 py-1 text-xs font-mono text-muted-foreground"
              >
                {s}
              </span>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">No sources recorded.</div>
        )}

        <RawJsonPanel data={entity.entity} triggerLabel="View raw response" />
      </div>
    </div>
  );
}
