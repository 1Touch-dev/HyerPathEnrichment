"use client";

import Image from "next/image";
import { initialsFrom, formatPercent } from "@/src/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { PhotoAsset } from "@/src/lib/types";

interface PhotoCardProps {
  photo: PhotoAsset | null;
  fallbackText: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function PhotoCard({ photo, fallbackText, size = "md", className = "" }: PhotoCardProps) {
  const sizeMap = {
    sm: { container: "w-14 h-14", text: "text-sm" },
    md: { container: "w-24 h-24", text: "text-lg" },
    lg: { container: "w-32 h-32", text: "text-2xl" },
  };

  const { container, text } = sizeMap[size];

  if (!photo || !photo.assetUrl) {
    // Fallback: Show initials
    return (
      <div
        className={`${container} flex items-center justify-center rounded-full bg-gradient-to-br from-primary/20 to-primary/10 ${text} font-semibold ${className}`}
      >
        {initialsFrom(fallbackText)}
      </div>
    );
  }

  // Format date for display
  const capturedDate = new Date(photo.capturedAt).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`relative ${container} ${className}`}>
            <Image
              src={photo.assetUrl}
              alt={fallbackText}
              width={size === "lg" ? 128 : size === "md" ? 96 : 56}
              height={size === "lg" ? 128 : size === "md" ? 96 : 56}
              unoptimized
              className="w-full h-full rounded-full object-cover ring-2 ring-offset-2 ring-primary/20 cursor-help"
            />
          </div>
        </TooltipTrigger>
        <TooltipContent side="right" className="space-y-1">
          <p className="font-semibold">Photo Details</p>
          <div className="space-y-0.5 text-xs">
            <div>
              <span className="text-muted-foreground">Source:</span> {photo.source}
            </div>
            <div>
              <span className="text-muted-foreground">Captured:</span> {capturedDate}
            </div>
            <div>
              <span className="text-muted-foreground">Confidence:</span>{" "}
              {formatPercent(photo.confidence)}
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
