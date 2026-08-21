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
  Briefcase,
  ShieldCheck,
  Users,
  ScrollText,
  Flag,
  ListTodo,
  BarChart3,
  Inbox,
  Building2,
  FileSearch,
  Layers,
  MailCheck,
  ClipboardList,
  GraduationCap,
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
    { href: "/app/practice", label: "Interview Prep", icon: GraduationCap },
    { href: "/app/history", label: "History", icon: History },
    { href: "/app/signals", label: "Signals", icon: Bell },
    { href: "/app/matches", label: "Matches", icon: Sparkles },
    { href: "/app/matches/swipe", label: "Swipe jobs", icon: Briefcase },
    { href: "/app/tracker", label: "Applications", icon: ClipboardList },
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
    { href: "/app/admin/review-queue", label: "Review queue", icon: Inbox },
    { href: "/app/admin/job-postings", label: "Job postings", icon: Building2 },
    { href: "/app/admin/documents", label: "Documents", icon: FileSearch },
    { href: "/app/admin/portfolio", label: "Portfolio", icon: Layers },
    { href: "/app/admin/outreach", label: "Outreach", icon: MailCheck },
  ],
};
