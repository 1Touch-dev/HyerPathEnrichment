import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const formatPercent = (value: number) => `${Math.round(value * 100)}%`;

export const tierLabels: Record<string, string> = {
  tier1: "LinkedIn Photo",
  tier2: "Username Discovery",
  tier3: "Deep OSINT",
  tier4: "Job & Business Intelligence",
};

export const initialsFrom = (value: string) =>
  value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");

export function copyToClipboard(text: string) {
  return navigator.clipboard.writeText(text);
}

export function getConfidenceColor(score: number): string {
  if (score >= 0.9) return "text-green-600 dark:text-green-400";
  if (score >= 0.7) return "text-yellow-600 dark:text-yellow-400";
  return "text-orange-600 dark:text-orange-400";
}

export function getConfidenceProgressColor(score: number): string {
  if (score >= 0.9) return "bg-green-600";
  if (score >= 0.7) return "bg-yellow-600";
  return "bg-orange-600";
}

export function getConfidenceBadgeVariant(score: number): "success" | "warning" | "destructive" {
  if (score >= 0.9) return "success";
  if (score >= 0.7) return "warning";
  return "destructive";
}

export function getSourceLabel(source: string): string {
  const sourceLabels: Record<string, string> = {
    linkedin_photo: "LinkedIn Photo",
    sherlock: "Sherlock (400+ sites)",
    maigret: "Maigret (3,000+ sites)",
    social_analyzer: "Social Analyzer",
    gitrecon: "GitHub Recon",
    theharvester: "theHarvester",
    email_sleuth: "Email Sleuth",
    email_discover: "Email Discovery",
    reacher: "Reacher (SMTP Verified)",
    email_verifier: "Email Verifier",
    crosslinked: "CrossLinked",
    jobspy: "JobSpy",
    google_maps: "Google Maps",
    local_business: "Local Business",
  };
  return sourceLabels[source] || source;
}

export function getPlatformDisplayName(platform: string): string {
  const platformNames: Record<string, string> = {
    linkedin: "LinkedIn",
    github: "GitHub",
    twitter: "Twitter",
    x: "X",
    facebook: "Facebook",
    instagram: "Instagram",
    reddit: "Reddit",
    youtube: "YouTube",
    tiktok: "TikTok",
    medium: "Medium",
    stackoverflow: "Stack Overflow",
    gitlab: "GitLab",
    bitbucket: "Bitbucket",
    behance: "Behance",
    dribbble: "Dribbble",
    pinterest: "Pinterest",
    snapchat: "Snapchat",
    telegram: "Telegram",
    whatsapp: "WhatsApp",
    discord: "Discord",
    twitch: "Twitch",
  };
  return platformNames[platform.toLowerCase()] || platform;
}
