import { CheckCircle, AlertCircle, Mail } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import { formatPercent, getConfidenceColor, getConfidenceProgressColor, cn } from "@/src/lib/utils";
import type { VerifiedEmail } from "@/src/lib/types";

interface EmailStatusCardProps {
  email: VerifiedEmail | string;
  onClick?: () => void;
  selected?: boolean;
}

export function EmailStatusCard({ email, onClick, selected }: EmailStatusCardProps) {
  const isVerified = typeof email !== "string";

  if (isVerified) {
    const verifiedEmail = email as VerifiedEmail;
    return (
      <Card
        className={cn(
          "cursor-pointer border-border/70 bg-card shadow-sm transition-all hover:shadow-md",
          selected ? "ring-2 ring-primary" : "",
        )}
        onClick={onClick}
      >
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 shrink-0 mt-0.5 text-success" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2 mb-2">
                <p className="font-medium text-sm truncate">{verifiedEmail.value}</p>
                <Badge variant="success" className="shrink-0">
                  Verified
                </Badge>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>Status: {verifiedEmail.status}</span>
                  <span>•</span>
                  <span>Source: {verifiedEmail.source}</span>
                </div>
                {/* Confidence bar */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">Confidence</span>
                    <span
                      className={cn(
                        "text-xs font-bold",
                        getConfidenceColor(verifiedEmail.confidence),
                      )}
                    >
                      {formatPercent(verifiedEmail.confidence)}
                    </span>
                  </div>
                  <div className="relative">
                    <Progress value={verifiedEmail.confidence * 100} className="h-1.5" />
                    <div
                      className={cn(
                        "absolute top-0 left-0 h-1.5 rounded-full transition-all",
                        getConfidenceProgressColor(verifiedEmail.confidence),
                      )}
                      style={{ width: `${verifiedEmail.confidence * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Unverified email
  return (
    <Card
      className={cn(
        "cursor-pointer border-border/70 bg-card shadow-sm transition-all hover:shadow-md",
        selected ? "ring-2 ring-primary" : "",
      )}
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-warning" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <p className="font-medium text-sm truncate">{email as string}</p>
              <Badge variant="warning" className="shrink-0">
                Unverified
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-1">Email found but not SMTP verified</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
