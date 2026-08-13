import {
  LayoutDashboard,
  History,
  Shield,
  Settings,
  Activity,
  Bell,
  Search,
  Sparkles,
  User,
  Mail,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  disabled?: boolean;
};

export type NavSection = {
  title: string;
  items: NavItem[];
};

export const mainNav: NavSection = {
  title: "Main",
  items: [
    { href: "/app/enrich", label: "Look up", icon: Search },
    { href: "/app/documents", label: "My CV", icon: Sparkles },
    { href: "/app/history", label: "History", icon: History },
    { href: "/app/signals", label: "Signals", icon: Bell },
    { href: "/app/matches", label: "Matches", icon: Sparkles },
    { href: "/app/portfolio", label: "Portfolio", icon: User },
    { href: "/app/outreach", label: "Outreach", icon: Mail },
  ],
};

export const systemNav: NavSection = {
  title: "System",
  items: [
    { href: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/app/privacy", label: "Privacy", icon: Shield },
    { href: "/app/settings", label: "Settings", icon: Settings },
    { href: "/app/health", label: "Health", icon: Activity },
  ],
};

export const allNavSections = [mainNav, systemNav];
