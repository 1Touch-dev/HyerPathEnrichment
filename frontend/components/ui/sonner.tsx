"use client";

import type { ComponentProps } from "react";
import { Toaster as Sonner } from "sonner";

type ToasterProps = ComponentProps<typeof Sonner>;

const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="light"
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:rounded-xl group-[.toaster]:border-border/70 group-[.toaster]:bg-surface group-[.toaster]:text-foreground group-[.toaster]:shadow-elevated",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-secondary group-[.toast]:text-secondary-foreground",
          error:
            "group-[.toaster]:border-destructive/20 group-[.toaster]:bg-destructive-soft group-[.toaster]:text-foreground",
          success:
            "group-[.toaster]:border-success/20 group-[.toaster]:bg-success-soft group-[.toaster]:text-foreground",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
