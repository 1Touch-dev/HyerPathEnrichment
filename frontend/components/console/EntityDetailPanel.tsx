"use client";

import { useState, type ReactNode } from "react";
import type { Dossier } from "@/src/lib/types";
import { RawJsonPanel } from "@/components/console/RawJsonPanel";
import { Badge } from "@/components/ui/badge";
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
    <div className="grid gap-2 border-b border-border/60 pb-3 last:border-0 last:pb-0 sm:grid-cols-[120px_minmax(0,1fr)] sm:gap-4">
      <div className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className="min-w-0 text-sm text-foreground break-words">{value}</div>
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
  const subtitle = "subtitle" in entity ? entity.subtitle : undefined;

  return (
    <div className="rounded-xl border border-border/70 bg-card p-5 shadow-panel">
      <div className="mb-5 space-y-3 border-b border-border/60 pb-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{detailLabel(entity.kind)}</Badge>
          {"confidence" in entity && typeof entity.confidence === "number" ? (
            <Badge
              variant={
                entity.confidence >= 0.9
                  ? "success"
                  : entity.confidence >= 0.7
                    ? "warning"
                    : "outline"
              }
            >
              {formatPercent(entity.confidence)}
            </Badge>
          ) : null}
        </div>
        <div>
          <h3 className="text-lg font-semibold tracking-tight text-foreground">{entity.title}</h3>
          {subtitle ? (
            <p className="mt-1 break-words text-sm text-muted-foreground">{subtitle}</p>
          ) : null}
        </div>
      </div>

      {entity.kind === "handle" ? (
        <>
          <div className="mb-4 flex items-center gap-2">
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
          <div className="mb-3 mt-3">
            <div className="mb-2 flex items-center justify-between">
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
          <div className="mb-3 mt-3">
            <div className="mb-2 flex items-center justify-between">
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
          <div className="mb-3 mt-3">
            <div className="mb-2 flex items-center justify-between">
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

      <div className="mt-5 flex flex-col gap-3 border-t border-border pt-5">
        <div className="text-sm font-semibold">Request sources</div>
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

function detailLabel(kind: DossierEntity["kind"]): string {
  switch (kind) {
    case "handle":
      return "Handle";
    case "verifiedEmail":
      return "Verified email";
    case "email":
      return "Email";
    case "job":
      return "Professional lead";
    case "confidence":
      return "Confidence rule";
    case "source":
      return "Source";
    default:
      return "Detail";
  }
}
