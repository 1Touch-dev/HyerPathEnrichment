import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/src/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md border border-transparent text-sm font-medium shadow-sm transition-[background-color,border-color,color,box-shadow,transform] duration-150 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/15 focus-visible:border-ring disabled:pointer-events-none disabled:opacity-50 active:translate-y-px",
  {
    variants: {
      variant: {
        // Contrast lock: filled primary/destructive always use *-foreground (white) text.
        default: "bg-primary text-primary-foreground hover:bg-primary/95 hover:shadow-panel",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/95 hover:shadow-panel",
        outline:
          "border-border bg-surface text-foreground shadow-none hover:border-ring/30 hover:bg-secondary/70",
        secondary:
          "border-border/70 bg-surface text-foreground shadow-none hover:bg-secondary hover:shadow-panel",
        ghost:
          "border-transparent bg-transparent text-foreground shadow-none hover:bg-secondary/70",
        link: "h-auto rounded-none border-0 bg-transparent p-0 text-primary shadow-none underline-offset-4 hover:underline",
        soft: "bg-primary-soft text-primary shadow-none hover:bg-primary-soft/80",
        success: "bg-success-soft text-success shadow-none hover:bg-success-soft/80",
      },
      size: {
        default: "h-11 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-12 rounded-md px-6",
        icon: "h-10 w-10",
        xs: "h-8 rounded-md px-2.5 text-xs",
      },
    },
    compoundVariants: [
      {
        variant: "link",
        size: "default",
        className: "h-auto px-0 py-0",
      },
    ],
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
