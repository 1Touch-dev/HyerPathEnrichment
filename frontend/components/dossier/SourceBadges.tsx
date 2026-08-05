import { Badge } from "@/components/ui/badge";
import { getSourceLabel } from "@/src/lib/utils";
import { Search, Mail, Circle, Building, Briefcase, MapPin } from "lucide-react";

interface SourceBadgesProps {
  sources: string[];
  className?: string;
}

function getSourceIcon(source: string) {
  const iconMap: Record<string, React.ReactNode> = {
    sherlock: <Search className="w-3 h-3" />,
    maigret: <Search className="w-3 h-3" />,
    social_analyzer: <Search className="w-3 h-3" />,
    gitrecon: <Circle className="w-3 h-3" />,
    github: <Circle className="w-3 h-3" />,
    theharvester: <Mail className="w-3 h-3" />,
    email_sleuth: <Mail className="w-3 h-3" />,
    email_discover: <Mail className="w-3 h-3" />,
    reacher: <Mail className="w-3 h-3" />,
    email_verifier: <Mail className="w-3 h-3" />,
    crosslinked: <Building className="w-3 h-3" />,
    jobspy: <Briefcase className="w-3 h-3" />,
    google_maps: <MapPin className="w-3 h-3" />,
    local_business: <MapPin className="w-3 h-3" />,
  };
  return iconMap[source] || <Search className="w-3 h-3" />;
}

export function SourceBadges({ sources, className }: SourceBadgesProps) {
  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <div className={className}>
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">
        Data Sources
      </p>
      <div className="flex flex-wrap gap-2">
        {sources.map((source) => (
          <Badge key={source} variant="outline" className="gap-1 font-mono text-xs">
            {getSourceIcon(source)}
            {getSourceLabel(source)}
          </Badge>
        ))}
      </div>
    </div>
  );
}
