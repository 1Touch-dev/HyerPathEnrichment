import * as React from "react";
import { cn } from "@/src/lib/utils";

const PageHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "flex flex-col gap-4 border-b border-border/70 pb-5 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
      {...props}
    />
  ),
);
PageHeader.displayName = "PageHeader";

const PageHeaderContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex min-w-0 flex-1 flex-col gap-2", className)} {...props} />
  ),
);
PageHeaderContent.displayName = "PageHeaderContent";

const PageHeaderEyebrow = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn(
      "text-xs font-semibold uppercase tracking-[0.18em] text-subtle-foreground",
      className,
    )}
    {...props}
  />
));
PageHeaderEyebrow.displayName = "PageHeaderEyebrow";

const PageHeaderTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h1
    ref={ref}
    className={cn("text-2xl font-semibold tracking-tight text-foreground sm:text-3xl", className)}
    {...props}
  />
));
PageHeaderTitle.displayName = "PageHeaderTitle";

const PageHeaderDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("max-w-3xl text-sm text-muted-foreground sm:text-base", className)}
    {...props}
  />
));
PageHeaderDescription.displayName = "PageHeaderDescription";

const PageHeaderActions = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("flex flex-wrap items-center gap-2 sm:justify-end", className)}
      {...props}
    />
  ),
);
PageHeaderActions.displayName = "PageHeaderActions";

export {
  PageHeader,
  PageHeaderContent,
  PageHeaderEyebrow,
  PageHeaderTitle,
  PageHeaderDescription,
  PageHeaderActions,
};
