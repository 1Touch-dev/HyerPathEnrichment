import * as React from "react";
import {
  PageHeader,
  PageHeaderActions,
  PageHeaderContent,
  PageHeaderDescription,
  PageHeaderEyebrow,
  PageHeaderTitle,
} from "@/components/ui/page-header";
import {
  SectionHeader,
  SectionHeaderActions,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderEyebrow,
  SectionHeaderTitle,
} from "@/components/ui/section-header";
import { cn } from "@/src/lib/utils";
import type { Product } from "@/src/lib/product-doors";

type ShellPageWidth = "shell" | "wide" | "full";
type ShellDensity = "comfortable" | "dense";
type ShellSectionSurface = "default" | "muted" | "elevated" | "plain";

export const SHELL_PRODUCT_META = {
  candidate: {
    label: "Candidate",
    description: "Candidate workspace",
    density: "comfortable",
    accentClass: "from-primary/18 via-primary-soft/12 to-transparent",
  },
  osint: {
    label: "OSINT",
    description: "Public-only lookup",
    density: "dense",
    accentClass: "from-info/16 via-primary-soft/10 to-transparent",
  },
  desk: {
    label: "Desk",
    description: "Staff operations",
    density: "dense",
    accentClass: "from-secondary/95 via-primary-soft/8 to-transparent",
  },
} satisfies Record<
  Product,
  { label: string; description: string; density: ShellDensity; accentClass: string }
>;

const SHELL_PAGE_WIDTHS: Record<Product, Record<ShellPageWidth, string>> = {
  candidate: {
    shell: "max-w-6xl",
    wide: "max-w-7xl",
    full: "max-w-none",
  },
  osint: {
    shell: "max-w-[92rem]",
    wide: "max-w-[104rem]",
    full: "max-w-none",
  },
  desk: {
    shell: "max-w-[104rem]",
    wide: "max-w-[116rem]",
    full: "max-w-none",
  },
};

const SHELL_DENSITY_GAPS: Record<ShellDensity, string> = {
  comfortable: "gap-8",
  dense: "gap-6",
};

const SHELL_SECTION_SURFACE_CLASSES: Record<ShellSectionSurface, string> = {
  default: "app-surface",
  muted: "app-surface-muted",
  elevated: "app-surface-elevated",
  plain: "rounded-xl",
};

type ShellViewportProps = React.HTMLAttributes<HTMLDivElement> & {
  product: Product;
};

export function ShellViewport({ product, className, children, ...props }: ShellViewportProps) {
  const meta = SHELL_PRODUCT_META[product];

  return (
    <div
      data-shell-viewport=""
      data-shell-product={product}
      className={cn("relative isolate min-h-full", className)}
      {...props}
    >
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute inset-x-0 top-0 h-40 rounded-[2rem] bg-gradient-to-b blur-3xl",
          meta.accentClass,
        )}
      />
      <div className="relative min-h-full px-4 py-4 pb-24 sm:px-6 sm:py-6 sm:pb-24 lg:px-8 lg:py-8 md:pb-10">
        {children}
      </div>
    </div>
  );
}

type ShellPageProps = React.HTMLAttributes<HTMLDivElement> & {
  product: Product;
  width?: ShellPageWidth;
};

export function ShellPage({
  product,
  width = "shell",
  className,
  children,
  ...props
}: ShellPageProps) {
  const meta = SHELL_PRODUCT_META[product];

  return (
    <div
      data-shell-page=""
      data-shell-product={product}
      data-shell-density={meta.density}
      data-shell-width={width}
      className={cn(
        "mx-auto flex w-full min-w-0 flex-col",
        SHELL_DENSITY_GAPS[meta.density],
        SHELL_PAGE_WIDTHS[product][width],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

type ShellPageHeaderProps = React.HTMLAttributes<HTMLDivElement>;

export const ShellPageHeader = React.forwardRef<HTMLDivElement, ShellPageHeaderProps>(
  ({ className, ...props }, ref) => (
    <PageHeader
      ref={ref}
      className={cn(
        "rounded-[1.25rem] border border-border/60 bg-surface/80 px-5 py-5 shadow-panel backdrop-blur-sm sm:px-6",
        className,
      )}
      {...props}
    />
  ),
);
ShellPageHeader.displayName = "ShellPageHeader";

type ShellSectionProps = React.HTMLAttributes<HTMLElement> & {
  surface?: ShellSectionSurface;
};

export const ShellSection = React.forwardRef<HTMLElement, ShellSectionProps>(
  ({ surface = "default", className, children, ...props }, ref) => (
    <section
      ref={ref}
      data-shell-section=""
      data-shell-surface={surface}
      className={cn(
        "flex min-w-0 flex-col gap-4",
        SHELL_SECTION_SURFACE_CLASSES[surface],
        surface === "plain" ? "" : "p-5 sm:p-6",
        className,
      )}
      {...props}
    >
      {children}
    </section>
  ),
);
ShellSection.displayName = "ShellSection";

export const ShellSectionHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <SectionHeader ref={ref} className={cn("gap-3", className)} {...props} />
));
ShellSectionHeader.displayName = "ShellSectionHeader";

export const ShellPageHeaderContent = PageHeaderContent;
export const ShellPageHeaderEyebrow = PageHeaderEyebrow;
export const ShellPageHeaderTitle = PageHeaderTitle;
export const ShellPageHeaderDescription = PageHeaderDescription;
export const ShellPageHeaderActions = PageHeaderActions;
export const ShellSectionHeaderContent = SectionHeaderContent;
export const ShellSectionHeaderEyebrow = SectionHeaderEyebrow;
export const ShellSectionHeaderTitle = SectionHeaderTitle;
export const ShellSectionHeaderDescription = SectionHeaderDescription;
export const ShellSectionHeaderActions = SectionHeaderActions;
