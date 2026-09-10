import * as React from "react";
import { cn } from "@/src/lib/utils";

const FilterBar = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-border/70 bg-surface p-3 shadow-sm sm:flex-row sm:items-end sm:justify-between sm:p-4",
        className,
      )}
      {...props}
    />
  ),
);
FilterBar.displayName = "FilterBar";

const FilterBarGroup = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("flex flex-1 flex-wrap items-end gap-3 sm:gap-4", className)}
      {...props}
    />
  ),
);
FilterBarGroup.displayName = "FilterBarGroup";

const FilterBarActions = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("flex flex-wrap items-center justify-start gap-2 sm:justify-end", className)}
      {...props}
    />
  ),
);
FilterBarActions.displayName = "FilterBarActions";

export { FilterBar, FilterBarGroup, FilterBarActions };
