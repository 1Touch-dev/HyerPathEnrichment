"use client";

import * as React from "react";
import { cn } from "@/src/lib/utils";

export interface RangeSliderProps extends Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  "type" | "value" | "onChange" | "min" | "max"
> {
  min: number;
  max: number;
  value: number;
  onValueChange: (value: number) => void;
}

export const RangeSlider = React.forwardRef<HTMLInputElement, RangeSliderProps>(
  ({ className, min, max, step = 1, value, onValueChange, id, ...props }, ref) => {
    const fillPercent =
      max === min ? 0 : Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));

    return (
      <div className={cn("relative h-6 w-full", className)}>
        <div
          className="pointer-events-none absolute left-0 right-0 top-1/2 h-2 -translate-y-1/2 overflow-hidden rounded-full bg-secondary"
          aria-hidden
        >
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-200 ease-out"
            style={{ width: `${fillPercent}%` }}
          />
        </div>
        <input
          ref={ref}
          id={id}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(event) => onValueChange(Number(event.target.value))}
          className="range-slider absolute inset-0 h-full w-full cursor-pointer"
          {...props}
        />
      </div>
    );
  },
);
RangeSlider.displayName = "RangeSlider";
