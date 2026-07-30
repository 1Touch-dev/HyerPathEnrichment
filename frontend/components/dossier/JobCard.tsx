import { MapPin, Wifi, Briefcase } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/src/lib/utils";
import type { JobListing } from "@/src/lib/types";

interface JobCardProps {
  job: JobListing;
  onClick?: () => void;
  selected?: boolean;
  className?: string;
}

export function JobCard({ job, onClick, selected, className }: JobCardProps) {
  return (
    <Card
      className={cn(
        "cursor-pointer transition-all hover:shadow-lg",
        selected ? "ring-2 ring-primary" : "",
        className,
      )}
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <div className="p-2 rounded-lg bg-primary/10 shrink-0">
              <Briefcase className="w-5 h-5 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="font-semibold text-base mb-1 truncate">{job.title}</h4>
              <p className="text-sm text-muted-foreground truncate">{job.company}</p>
            </div>
          </div>
          {job.remote && (
            <Badge variant="secondary" className="gap-1 shrink-0">
              <Wifi className="w-3 h-3" />
              Remote
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <MapPin className="w-4 h-4 shrink-0" />
            <span className="truncate">{job.location}</span>
            {!job.remote && (
              <>
                <span>•</span>
                <span>On-site</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-xs">
              {job.source}
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
