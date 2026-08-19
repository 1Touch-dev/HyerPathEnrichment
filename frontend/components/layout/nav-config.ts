import {
  LayoutDashboard,
  History,
  Shield,
  Settings,
  Activity,
  Bell,
  Search,
  Sparkles,
  FileText,
  User,
  Mail,
  Briefcase,
  ShieldCheck,
  Users,
  ScrollText,
  Flag,
  ListTodo,
  BarChart3,
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
    { href: "/app/documents", label: "Documents", icon: FileText },
    { href: "/app/history", label: "History", icon: History },
    { href: "/app/signals", label: "Signals", icon: Bell },
    { href: "/app/matches", label: "Matches", icon: Sparkles },
    { href: "/app/matches/swipe", label: "Swipe jobs", icon: Briefcase },
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

export const adminNav: NavSection = {
  title: "Admin",
  items: [
    { href: "/app/admin/system-health", label: "System health", icon: Activity },
    { href: "/app/admin/users", label: "Users", icon: Users },
    { href: "/app/admin/roles", label: "Roles", icon: ShieldCheck },
    { href: "/app/admin/audit-logs", label: "Audit logs", icon: ScrollText },
    { href: "/app/admin/feature-flags", label: "Feature flags", icon: Flag },
    { href: "/app/admin/queues", label: "Queues", icon: ListTodo },
    { href: "/app/admin/analytics", label: "Analytics", icon: BarChart3 },
  ],
};
