"use client";

import { useState, type ReactNode } from "react";
import type { Dossier } from "@/src/lib/types";
import { RawJsonPanel } from "@/components/console/RawJsonPanel";
import {
  formatPercent,
  copyToClipboard,
  cn,
  getConfidenceColor,
  getConfidenceProgressColor,
} from "@/src/lib/utils";
import { PlatformIcon } from "@/components/dossier/PlatformIcon";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Copy, Check, ChevronDown } from "lucide-react";
import type { DossierEntity } from "./dossier-entity";

type EntityDetailPanelProps = {
  dossier: Dossier;
  entity: DossierEntity;
};

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start gap-4 mb-3">
      <div className="w-28 shrink-0 text-xs font-medium uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className="min-w-0 flex-1 text-sm text-foreground break-words">{value}</div>
    </div>
  );
}

function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await copyToClipboard(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button variant="ghost" size="sm" onClick={handleCopy} className="h-7 px-2">
      {copied ? (
        <>
          <Check className="w-3 h-3 mr-1" />
          Copied
        </>
      ) : (
        <>
          <Copy className="w-3 h-3 mr-1" />
          {label || "Copy"}
        </>
      )}
    </Button>
  );
}

export function EntityDetailPanel({ dossier, entity }: EntityDetailPanelProps) {
  const [metadataOpen, setMetadataOpen] = useState(false);

  return (
    <div className="rounded-lg border bg-card p-5">
      {entity.kind === "handle" ? (
        <>
          <div className="flex items-center gap-2 mb-4">
            <PlatformIcon platform={entity.entity.platform} className="w-6 h-6" />
            <h3 className="font-semibold text-lg">{entity.entity.platform}</h3>
          </div>
          <Field label="Type" value="Social Handle" />
          <Field
            label="Username"
            value={
              <div className="flex items-center gap-2">
                <span>{entity.entity.username}</span>
                <CopyButton text={entity.entity.username} />
              </div>
            }
          />
          <Field
            label="Profile"
            value={
              <div className="flex items-center gap-2">
                <a
                  href={entity.entity.profileUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary underline truncate"
                >
                  {entity.entity.profileUrl}
                </a>
                <CopyButton text={entity.entity.profileUrl} />
              </div>
            }
          />
          <div className="mb-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                Confidence
              </span>
              <span
                className={cn("text-sm font-bold", getConfidenceColor(entity.entity.confidence))}
              >
                {formatPercent(entity.entity.confidence)}
              </span>
            </div>
            <div className="relative">
              <Progress value={entity.entity.confidence * 100} className="h-2" />
              <div
                className={cn(
                  "absolute top-0 left-0 h-2 rounded-full transition-all",
                  getConfidenceProgressColor(entity.entity.confidence),
                )}
                style={{ width: `${entity.entity.confidence * 100}%` }}
              />
            </div>
          </div>
          {entity.entity.metadata && Object.keys(entity.entity.metadata).length > 0 && (
            <Collapsible open={metadataOpen} onOpenChange={setMetadataOpen}>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" size="sm" className="w-full justify-between">
                  <span className="text-xs font-medium uppercase tracking-widest">Metadata</span>
                  <ChevronDown
                    className={cn("w-4 h-4 transition-transform", metadataOpen && "rotate-180")}
                  />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2">
                <div className="rounded-lg bg-muted p-3">
                  <pre className="font-mono text-xs overflow-x-auto">
                    {JSON.stringify(entity.entity.metadata, null, 2)}
                  </pre>
                </div>
              </CollapsibleContent>
            </Collapsible>
          )}
        </>
      ) : null}

      {entity.kind === "verifiedEmail" ? (
        <>
          <Field label="Type" value="Verified Email" />
          <Field
            label="Email"
            value={
              <div className="flex items-center gap-2">
                <span>{entity.entity.value}</span>
                <CopyButton text={entity.entity.value} />
              </div>
            }
          />
          <Field label="Status" value={entity.entity.status} />
          <Field label="Source" value={entity.entity.source} />
          <div className="mb-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                Confidence
              </span>
              <span
                className={cn("text-sm font-bold", getConfidenceColor(entity.entity.confidence))}
              >
                {formatPercent(entity.entity.confidence)}
              </span>
            </div>
            <div className="relative">
              <Progress value={entity.entity.confidence * 100} className="h-2" />
              <div
                className={cn(
                  "absolute top-0 left-0 h-2 rounded-full transition-all",
                  getConfidenceProgressColor(entity.entity.confidence),
                )}
                style={{ width: `${entity.entity.confidence * 100}%` }}
              />
            </div>
          </div>
        </>
      ) : null}

      {entity.kind === "email" ? (
        <>
          <Field label="Type" value="Email" />
          <Field
            label="Email"
            value={
              <div className="flex items-center gap-2">
                <span>{entity.entity}</span>
                <CopyButton text={entity.entity} />
              </div>
            }
          />
          <Field label="Status" value="Unverified" />
        </>
      ) : null}

      {entity.kind === "job" ? (
        <>
          <Field label="Type" value="Job Listing" />
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
          <Field label="Type" value="Confidence Rule" />
          <Field label="Label" value={entity.entity.label} />
          <div className="mb-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                Score
              </span>
              <span className={cn("text-sm font-bold", getConfidenceColor(entity.entity.score))}>
                {formatPercent(entity.entity.score)}
              </span>
            </div>
            <div className="relative">
              <Progress value={entity.entity.score * 100} className="h-2" />
              <div
                className={cn(
                  "absolute top-0 left-0 h-2 rounded-full transition-all",
                  getConfidenceProgressColor(entity.entity.score),
                )}
                style={{ width: `${entity.entity.score * 100}%` }}
              />
            </div>
          </div>
          <Field
            label="Evidence"
            value={
              <div className="flex flex-wrap gap-1">
                {entity.entity.evidence.map((ev, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center rounded-md bg-muted px-2 py-1 text-xs"
                  >
                    {ev}
                  </span>
                ))}
              </div>
            }
          />
        </>
      ) : null}

      {entity.kind === "source" ? (
        <>
          <Field label="Type" value="Data Source" />
          <Field label="Name" value={<span className="font-mono text-xs">{entity.entity}</span>} />
        </>
      ) : null}

      <div className="mt-4 flex flex-col gap-3 pt-4 border-t border-border">
        <div className="text-sm font-semibold">Job Sources</div>
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
