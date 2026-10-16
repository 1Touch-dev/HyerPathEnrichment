"use client";

import { resolveThemeVars } from "./theme";
import { TEMPLATE_COMPONENTS } from "./registry";
import type { PortfolioRenderModel } from "./types";

interface PortfolioRendererProps {
  model: PortfolioRenderModel;
  preview?: boolean;
  className?: string;
}

export function PortfolioRenderer({ model, preview = false, className }: PortfolioRendererProps) {
  const Template =
    TEMPLATE_COMPONENTS[model.templateId] ?? TEMPLATE_COMPONENTS.minimal_professional;
  const vars = resolveThemeVars(model.theme);

  return (
    <div
      className={className}
      style={vars as React.CSSProperties}
      data-portfolio-template={model.templateId}
    >
      <Template model={model} preview={preview} />
    </div>
  );
}
