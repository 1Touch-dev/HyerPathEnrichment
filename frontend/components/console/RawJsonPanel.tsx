"use client";

import { useState } from "react";
import { Copy, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { EnrichmentJob } from "@/src/lib/types";
import { copyToClipboard } from "@/src/lib/utils";

type RawJsonPanelProps = {
  job?: EnrichmentJob;
  data?: unknown;
  triggerLabel?: string;
  defaultOpen?: boolean;
  showCopy?: boolean;
};

export function RawJsonPanel({
  job,
  data,
  triggerLabel = "Raw JSON",
  defaultOpen = false,
  showCopy = true,
}: RawJsonPanelProps) {
  // Back-compat: older callsites passed `job`. New callsites can pass `data`.
  const jsonTarget = data ?? job;
  const json = jsonTarget ? JSON.stringify(jsonTarget, null, 2) : "";

  const [open, setOpen] = useState(defaultOpen);

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded-lg border">
      <div className="flex items-center justify-between px-4 py-3">
        <CollapsibleTrigger asChild>
          <Button variant="ghost" size="sm" className="gap-2 px-0">
            {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
            {triggerLabel}
          </Button>
        </CollapsibleTrigger>
        {showCopy && json ? (
          <Button variant="outline" size="sm" onClick={() => void copyToClipboard(json)}>
            <Copy className="mr-1 size-3" />
            Copy
          </Button>
        ) : null}
      </div>
      <CollapsibleContent>
        <pre className="max-h-96 overflow-auto border-t bg-muted/30 p-4 text-xs">{json}</pre>
      </CollapsibleContent>
    </Collapsible>
  );
}
