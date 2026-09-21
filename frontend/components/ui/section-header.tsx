import * as React from "react";
import { cn } from "@/src/lib/utils";

const SectionHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
      {...props}
    />
  ),
);
SectionHeader.displayName = "SectionHeader";

const SectionHeaderContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex min-w-0 flex-1 flex-col gap-1.5", className)} {...props} />
  ),
);
SectionHeaderContent.displayName = "SectionHeaderContent";

const SectionHeaderEyebrow = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn(
      "text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-subtle-foreground",
      className,
    )}
    {...props}
  />
));
SectionHeaderEyebrow.displayName = "SectionHeaderEyebrow";

const SectionHeaderTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h2
    ref={ref}
    className={cn("text-lg font-semibold tracking-tight text-foreground", className)}
    {...props}
  />
));
SectionHeaderTitle.displayName = "SectionHeaderTitle";

const SectionHeaderDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
));
SectionHeaderDescription.displayName = "SectionHeaderDescription";

const SectionHeaderActions = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-wrap items-center gap-2", className)} {...props} />
  ),
);
SectionHeaderActions.displayName = "SectionHeaderActions";

export {
  SectionHeader,
  SectionHeaderContent,
  SectionHeaderEyebrow,
  SectionHeaderTitle,
  SectionHeaderDescription,
  SectionHeaderActions,
};
