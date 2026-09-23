"use client";

import { EnrichMode } from "@/src/lib/types";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { cn } from "@/src/lib/utils";

type EnrichModeToggleProps = {
  mode: EnrichMode;
  onChange: (mode: EnrichMode) => void;
};

export function EnrichModeToggle({ mode, onChange }: EnrichModeToggleProps) {
  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-primary">
          Enrichment mode
        </p>
        <p className="text-sm text-muted-foreground">
          Full async runs all tiers including Tier 1 browser pipeline.
        </p>
      </div>
      <RadioGroup
        value={mode}
        onValueChange={(value) => onChange(value as EnrichMode)}
        className="grid gap-3 sm:grid-cols-2"
      >
        <label
          className={cn(
            "flex cursor-pointer items-start gap-3 rounded-xl border border-border/70 bg-card p-4 shadow-sm transition-colors hover:bg-primary-soft/50",
            mode === "async" && "border-primary/40 bg-primary-soft",
          )}
        >
          <RadioGroupItem value="async" id="mode-async" className="mt-1" />
          <div>
            <Label htmlFor="mode-async" className="cursor-pointer">
              Full (async)
            </Label>
            <p className="text-xs text-muted-foreground">
              Queued job with live polling. All tiers available.
            </p>
          </div>
        </label>
        <label
          className={cn(
            "flex cursor-pointer items-start gap-3 rounded-xl border border-border/70 bg-card p-4 shadow-sm transition-colors hover:bg-primary-soft/50",
            mode === "sync" && "border-primary/40 bg-primary-soft",
          )}
        >
          <RadioGroupItem value="sync" id="mode-sync" className="mt-1" />
          <div>
            <Label htmlFor="mode-sync" className="cursor-pointer">
              Quick (sync)
            </Label>
            <p className="text-xs text-muted-foreground">
              Immediate response. Tier 1 excluded (browser required).
            </p>
          </div>
        </label>
      </RadioGroup>
    </div>
  );
}
