"use client";

import { cn, formatPercent, getConfidenceColor, getConfidenceProgressColor } from "@/src/lib/utils";
import { PlatformIcon } from "@/components/dossier/PlatformIcon";
import { Progress } from "@/components/ui/progress";

type ResultRowProps = {
  title: string;
  subtitle?: string;
  confidence?: number;
  selected?: boolean;
  onClick?: () => void;
  platform?: string;
};

export function ResultRow({
  title,
  subtitle,
  confidence,
  selected,
  onClick,
  platform,
}: ResultRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full rounded-lg border px-4 py-3 text-left transition-all hover:bg-muted hover:shadow-md",
        selected ? "border-primary bg-secondary/60 ring-2 ring-primary/20" : "border-border",
      )}
    >
      <div className="flex items-start gap-3">
        {/* Platform Icon */}
        {platform && (
          <div className="shrink-0 mt-0.5">
            <PlatformIcon platform={platform} />
          </div>
        )}

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="truncate text-sm font-medium">{title}</div>
          {subtitle ? (
            <div className="mt-1 truncate font-mono text-xs text-muted-foreground">{subtitle}</div>
          ) : null}

          {/* Confidence Progress Bar */}
          {confidence !== undefined && (
            <div className="mt-2 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Confidence</span>
                <span className={cn("text-xs font-bold", getConfidenceColor(confidence))}>
                  {formatPercent(confidence)}
                </span>
              </div>
              <div className="relative">
                <Progress value={confidence * 100} className="h-1.5" />
                <div
                  className={cn(
                    "absolute top-0 left-0 h-1.5 rounded-full transition-all",
                    getConfidenceProgressColor(confidence),
                  )}
                  style={{ width: `${confidence * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </button>
  );
}
