import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import {
  PageHeader,
  PageHeaderActions,
  PageHeaderContent,
  PageHeaderDescription,
  PageHeaderEyebrow,
  PageHeaderTitle,
} from "@/components/ui/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/src/lib/utils";

type DeskPageProps = {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

type DeskMetricTone = "default" | "success" | "warning" | "danger" | "info";

const metricToneClasses: Record<DeskMetricTone, string> = {
  default: "border-border/70 bg-card",
  success: "border-success/20 bg-success/10",
  warning: "border-warning/20 bg-warning/10",
  danger: "border-destructive/20 bg-destructive/10",
  info: "border-info/20 bg-info/10",
};

export function DeskPage({
  eyebrow,
  title,
  description,
  actions,
  children,
  className,
}: DeskPageProps) {
  return (
    <div className={cn("flex flex-col gap-6", className)}>
      <PageHeader>
        <PageHeaderContent>
          <PageHeaderEyebrow>{eyebrow}</PageHeaderEyebrow>
          <PageHeaderTitle>{title}</PageHeaderTitle>
          <PageHeaderDescription>{description}</PageHeaderDescription>
        </PageHeaderContent>
        {actions ? <PageHeaderActions>{actions}</PageHeaderActions> : null}
      </PageHeader>
      {children}
    </div>
  );
}

export function DeskMetricGrid({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid gap-3 sm:grid-cols-2 xl:grid-cols-4", className)}>{children}</div>
  );
}

export function DeskMetricCard({
  label,
  value,
  hint,
  tone = "default",
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: DeskMetricTone;
  className?: string;
}) {
  return (
    <Card className={cn("shadow-sm", metricToneClasses[tone], className)}>
      <CardContent className="flex min-h-28 flex-col justify-between gap-3 p-5">
        <div className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-subtle-foreground">
          {label}
        </div>
        <div className="space-y-1">
          <div className="text-2xl font-semibold tracking-tight text-foreground">{value}</div>
          {hint ? <div className="text-sm text-muted-foreground">{hint}</div> : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function DeskPagination({
  canPrevious,
  canNext,
  onPrevious,
  onNext,
  previousLabel = "Previous",
  nextLabel = "Next page",
}: {
  canPrevious: boolean;
  canNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
  previousLabel?: string;
  nextLabel?: string;
}) {
  return (
    <div className="flex items-center justify-end gap-2">
      <Button variant="outline" size="sm" disabled={!canPrevious} onClick={onPrevious}>
        {previousLabel}
      </Button>
      <Button variant="outline" size="sm" disabled={!canNext} onClick={onNext}>
        {nextLabel}
      </Button>
    </div>
  );
}
