import type { PortfolioPaletteId, PortfolioThemeConfig } from "@/src/lib/types";

const PALETTES: Record<
  PortfolioPaletteId,
  { bg: string; surface: string; text: string; muted: string; accent: string; border: string }
> = {
  neutral: {
    bg: "#fafaf9",
    surface: "#ffffff",
    text: "#1c1917",
    muted: "#78716c",
    accent: "#44403c",
    border: "#e7e5e4",
  },
  vibrant: {
    bg: "#0f0a1a",
    surface: "#1a1229",
    text: "#fdf4ff",
    muted: "#d8b4fe",
    accent: "#f472b6",
    border: "#4c1d95",
  },
  ocean: {
    bg: "#0b1220",
    surface: "#111827",
    text: "#e5e7eb",
    muted: "#94a3b8",
    accent: "#38bdf8",
    border: "#1e293b",
  },
  forest: {
    bg: "#f4f7f4",
    surface: "#ffffff",
    text: "#14201a",
    muted: "#5b6b61",
    accent: "#2f6f4e",
    border: "#d7e3db",
  },
  slate: {
    bg: "#f8fafc",
    surface: "#ffffff",
    text: "#0f172a",
    muted: "#64748b",
    accent: "#1e3a5f",
    border: "#e2e8f0",
  },
};

const FONT_STACKS: Record<PortfolioThemeConfig["fontPairing"], { display: string; body: string }> =
  {
    sans: {
      display: '"IBM Plex Sans", "Segoe UI", sans-serif',
      body: '"IBM Plex Sans", "Segoe UI", sans-serif',
    },
    serif: {
      display: 'Georgia, "Times New Roman", serif',
      body: '"IBM Plex Sans", "Segoe UI", sans-serif',
    },
    mono: {
      display: '"IBM Plex Mono", ui-monospace, monospace',
      body: '"IBM Plex Sans", "Segoe UI", sans-serif',
    },
    editorial: {
      display: 'Georgia, "Iowan Old Style", serif',
      body: 'Georgia, "Iowan Old Style", serif',
    },
  };

export function resolveThemeVars(theme: PortfolioThemeConfig): Record<string, string> {
  const palette = PALETTES[theme.palette] ?? PALETTES.neutral;
  const fonts = FONT_STACKS[theme.fontPairing] ?? FONT_STACKS.sans;
  const accent = theme.accent?.trim() || palette.accent;
  return {
    ["--pf-bg"]: palette.bg,
    ["--pf-surface"]: palette.surface,
    ["--pf-text"]: palette.text,
    ["--pf-muted"]: palette.muted,
    ["--pf-accent"]: accent,
    ["--pf-border"]: palette.border,
    ["--pf-font-display"]: fonts.display,
    ["--pf-font-body"]: fonts.body,
  };
}

export function isSectionVisible(
  key: string,
  visibility: Record<string, boolean>,
  hasContent: boolean,
): boolean {
  if (!hasContent) return false;
  return visibility[key] !== false;
}
