import {
  Circle,
  MessageSquare,
  Music,
  BookOpen,
  Code,
  GitBranch,
  Package,
  Palette,
  PenTool,
  Image,
  Camera,
  Send,
  MessageCircle,
  Headphones,
  User,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/src/lib/utils";

interface PlatformIconProps {
  platform: string;
  className?: string;
}

export function PlatformIcon({ platform, className }: PlatformIconProps) {
  const iconMap: Record<string, { icon: LucideIcon; color: string }> = {
    linkedin: { icon: Circle, color: "text-blue-600 dark:text-blue-400" },
    github: { icon: Circle, color: "text-gray-900 dark:text-gray-100" },
    twitter: { icon: Circle, color: "text-blue-400 dark:text-blue-300" },
    x: { icon: Circle, color: "text-gray-900 dark:text-gray-100" },
    facebook: { icon: Circle, color: "text-blue-700 dark:text-blue-500" },
    instagram: { icon: Circle, color: "text-pink-600 dark:text-pink-400" },
    reddit: { icon: MessageSquare, color: "text-orange-500 dark:text-orange-400" },
    youtube: { icon: Circle, color: "text-red-600 dark:text-red-500" },
    tiktok: { icon: Music, color: "text-gray-900 dark:text-gray-100" },
    medium: { icon: BookOpen, color: "text-gray-900 dark:text-gray-100" },
    stackoverflow: { icon: Code, color: "text-orange-500 dark:text-orange-400" },
    gitlab: { icon: GitBranch, color: "text-orange-600 dark:text-orange-400" },
    bitbucket: { icon: Package, color: "text-blue-600 dark:text-blue-400" },
    behance: { icon: Palette, color: "text-blue-600 dark:text-blue-400" },
    dribbble: { icon: PenTool, color: "text-pink-500 dark:text-pink-400" },
    pinterest: { icon: Image, color: "text-red-600 dark:text-red-500" },
    snapchat: { icon: Camera, color: "text-yellow-400 dark:text-yellow-300" },
    telegram: { icon: Send, color: "text-blue-500 dark:text-blue-400" },
    whatsapp: { icon: MessageCircle, color: "text-green-600 dark:text-green-500" },
    discord: { icon: MessageCircle, color: "text-indigo-600 dark:text-indigo-400" },
    twitch: { icon: Headphones, color: "text-purple-600 dark:text-purple-400" },
  };

  const platformKey = platform.toLowerCase();
  const config = iconMap[platformKey] || { icon: User, color: "text-muted-foreground" };
  const Icon = config.icon;

  return <Icon className={cn("w-4 h-4", config.color, className)} />;
}
