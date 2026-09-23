import { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";

type EmptyStateProps = {
  title: string;
  description?: string;
  action?: ReactNode;
};

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <Card className="border-dashed border-border/70 bg-card shadow-sm">
      <CardContent className="flex flex-col items-start gap-4 py-10 sm:py-12">
        <div className="flex max-w-2xl flex-col gap-2">
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-primary">
            Nothing here yet
          </p>
          <h3 className="text-lg font-semibold tracking-tight text-foreground">{title}</h3>
          {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
        </div>
        {action ? <div className="flex flex-wrap items-center gap-3">{action}</div> : null}
      </CardContent>
    </Card>
  );
}
