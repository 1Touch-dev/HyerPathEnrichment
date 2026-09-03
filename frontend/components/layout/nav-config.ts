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
  Send,
  Bot,
  UserSearch,
  Globe,
  Store,
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
  title: "Desk",
  items: [
    { href: "/desk/system-health", label: "System health", icon: Activity },
    { href: "/desk/users", label: "Users", icon: Users },
    { href: "/desk/roles", label: "Roles", icon: ShieldCheck },
    { href: "/desk/staff-invites", label: "Staff invites", icon: Mail },
    { href: "/desk/brands", label: "Brands", icon: Store },
    { href: "/desk/audit-logs", label: "Audit logs", icon: ScrollText },
    { href: "/desk/feature-flags", label: "Feature flags", icon: Flag },
    { href: "/desk/queues", label: "Queues", icon: ListTodo },
    { href: "/desk/analytics", label: "Analytics", icon: BarChart3 },
    { href: "/desk/review-queue", label: "Review queue", icon: Inbox },
    { href: "/desk/job-postings", label: "Job postings", icon: Building2 },
    { href: "/desk/documents", label: "Documents", icon: FileSearch },
    { href: "/desk/portfolio", label: "Portfolio", icon: Layers },
    { href: "/desk/outreach", label: "Outreach", icon: MailCheck },
    { href: "/desk/linkedin-tasks", label: "LinkedIn tasks", icon: Send },
    { href: "/desk/ai-actions", label: "AI actions", icon: Bot },
    { href: "/desk/sourcing-leads", label: "Sourcing leads", icon: UserSearch },
    { href: "/desk/demand-intelligence", label: "Demand intelligence", icon: Globe },
  ],
};
