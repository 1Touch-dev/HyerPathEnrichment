"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const SLUG_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;

interface SlugFieldProps {
  value: string;
  onChange: (value: string) => void;
}

export function SlugField({ value, onChange }: SlugFieldProps) {
  const isValid = value.length === 0 || (value.length >= 3 && value.length <= 60 && SLUG_PATTERN.test(value));

  return (
    <div>
      <Label htmlFor="slug">Portfolio URL</Label>
      <div className="flex items-center gap-1 text-sm text-muted-foreground">
        <span>hyrepath.dev/p/</span>
        <Input
          id="slug"
          value={value}
          onChange={(e) => onChange(e.target.value.toLowerCase())}
          className="w-48"
          aria-invalid={!isValid}
        />
      </div>
      {!isValid && (
        <p className="mt-1 text-xs text-destructive">
          3-60 characters: lowercase letters, numbers, and single hyphens between words.
        </p>
      )}
    </div>
  );
}
