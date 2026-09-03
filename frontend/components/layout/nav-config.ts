import {
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
import {
  filterByPermissions,
  type Permission,
  type Product,
  type ProductDoorUser,
} from "@/src/lib/product-doors";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  ownerOnly?: boolean;
  permission?: Permission;
  mobilePrimary?: boolean;
};

export type NavSection = {
  title: string;
  items: NavItem[];
};

const candidateMainNav: NavSection = {
  title: "Main",
  items: [
    { href: "/app/documents", label: "My CV", icon: Sparkles, mobilePrimary: true },
    { href: "/app/practice", label: "Interview Prep", icon: GraduationCap },
    { href: "/app/matches", label: "Matches", icon: Sparkles, mobilePrimary: true },
    { href: "/app/matches/swipe", label: "Swipe jobs", icon: Briefcase },
    {
      href: "/app/tracker",
      label: "Applications",
      icon: ClipboardList,
      mobilePrimary: true,
    },
    { href: "/app/portfolio", label: "Portfolio", icon: User },
    { href: "/app/outreach", label: "Outreach", icon: Mail },
  ],
};

const candidateSystemNav: NavSection = {
  title: "System",
  items: [
    { href: "/app/privacy", label: "Privacy", icon: Shield },
    { href: "/app/settings", label: "Settings", icon: Settings },
  ],
};

const osintNav: NavSection[] = [
  {
    title: "OSINT",
    items: [{ href: "/osint", label: "Look up", icon: Search, mobilePrimary: true }],
  },
  {
    title: "System",
    items: [{ href: "/osint/settings", label: "Settings", icon: Settings }],
  },
];

const deskNav: NavSection = {
  title: "Desk",
  items: [
    {
      href: "/desk/sourcing-leads",
      label: "Sourcing leads",
      icon: UserSearch,
      permission: { resource: "linkedin_sourcing", action: "write" },
      mobilePrimary: true,
    },
    {
      href: "/desk/brands",
      label: "Brands",
      icon: Store,
      permission: { resource: "brands", action: "read" },
      mobilePrimary: true,
    },
    {
      href: "/desk/users",
      label: "Users",
      icon: Users,
      permission: { resource: "users", action: "read" },
      mobilePrimary: true,
    },
    {
      href: "/desk/system-health",
      label: "System health",
      icon: Activity,
      permission: { resource: "system_health", action: "read" },
    },
    {
      href: "/desk/roles",
      label: "Roles",
      icon: ShieldCheck,
      ownerOnly: true,
    },
    {
      href: "/desk/staff-invites",
      label: "Staff invites",
      icon: Mail,
      permission: { resource: "users", action: "write" },
    },
    {
      href: "/desk/audit-logs",
      label: "Audit logs",
      icon: ScrollText,
      permission: { resource: "audit_logs", action: "read" },
    },
    {
      href: "/desk/feature-flags",
      label: "Feature flags",
      icon: Flag,
      ownerOnly: true,
    },
    {
      href: "/desk/queues",
      label: "Queues",
      icon: ListTodo,
      ownerOnly: true,
    },
    {
      href: "/desk/analytics",
      label: "Analytics",
      icon: BarChart3,
      permission: { resource: "analytics", action: "read" },
    },
    {
      href: "/desk/review-queue",
      label: "Review queue",
      icon: Inbox,
      permission: { resource: "content_review", action: "read" },
    },
    {
      href: "/desk/job-postings",
      label: "Job postings",
      icon: Building2,
      permission: { resource: "job_postings", action: "read" },
    },
    {
      href: "/desk/documents",
      label: "Documents",
      icon: FileSearch,
      permission: { resource: "documents", action: "read" },
    },
    {
      href: "/desk/portfolio",
      label: "Portfolio",
      icon: Layers,
      permission: { resource: "portfolio", action: "read" },
    },
    {
      href: "/desk/outreach",
      label: "Outreach",
      icon: MailCheck,
      permission: { resource: "outreach", action: "read" },
    },
    {
      href: "/desk/linkedin-tasks",
      label: "LinkedIn tasks",
      icon: Send,
      permission: { resource: "linkedin_tasks", action: "operate" },
    },
    {
      href: "/desk/ai-actions",
      label: "AI actions",
      icon: Bot,
      permission: { resource: "ai_supervision", action: "read" },
    },
    { href: "/desk/demand-intelligence", label: "Demand intelligence", icon: Globe },
    { href: "/desk/signals", label: "Signals", icon: Bell },
  ],
};

export function getNavSections(
  product: Product,
  user: ProductDoorUser | null | undefined,
): NavSection[] {
  if (product === "candidate") {
    return [candidateMainNav, candidateSystemNav];
  }
  if (product === "osint") {
    return osintNav;
  }
  return [{ ...deskNav, items: filterByPermissions(deskNav.items, user) }];
}
