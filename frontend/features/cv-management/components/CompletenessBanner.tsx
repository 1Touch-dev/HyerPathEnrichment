"use client";

import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { useCvCompleteness } from "../hooks/useCvCompleteness";

interface CompletenessBannerProps {
  documentId: string;
  onStartChat: () => void;
}

export function CompletenessBanner({ documentId, onStartChat }: CompletenessBannerProps) {
  const { data, isLoading } = useCvCompleteness(documentId);

  if (isLoading || !data) return null;
  if (data.missingFields.length === 0) return null; // fully complete — nothing to show (§8.1)

  const percent = Math.round(data.completenessScore * 100);

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-amber-900">
          Your CV is {percent}% complete — {data.missingFields.length} field
          {data.missingFields.length === 1 ? "" : "s"} missing
        </p>
        <Button size="sm" onClick={onStartChat}>
          Complete it
        </Button>
      </div>
      <Progress value={percent} className="mt-2" />
    </div>
  );
}
