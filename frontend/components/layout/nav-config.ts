import {
  LayoutDashboard,
  PlusCircle,
  History,
  Shield,
  Settings,
  Activity,
  Sparkles,
  LifeBuoy,
  LogOut,
  FileSearch,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

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
  title: 'MAIN',
  items: [
    { href: '/app', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/app/enrich', label: 'New Enrichment', icon: PlusCircle },
    { href: '/app/history', label: 'History', icon: History },
    { href: '/app/jobs', label: 'Results', icon: FileSearch },
  ],
};

export const systemNav: NavSection = {
  title: 'SYSTEM',
  items: [
    { href: '/app/privacy', label: 'Privacy', icon: Shield },
    { href: '/app/settings', label: 'Settings', icon: Settings },
    { href: '/app/health', label: 'System Health', icon: Activity },
  ],
};

export const footerNav: NavItem[] = [
  { href: '#upgrade', label: 'Upgrade', icon: Sparkles, disabled: true },
  { href: '#support', label: 'Support', icon: LifeBuoy, disabled: true },
  { href: '#signout', label: 'Sign out', icon: LogOut, disabled: true },
];

export const allNavSections = [mainNav, systemNav];
