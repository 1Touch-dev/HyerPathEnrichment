'use client';

import Link from 'next/link';
import { MoreHorizontal } from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { mainNav, systemNav } from './nav-config';

type AppBottomNavProps = {
  pathname: string;
};

export function AppBottomNav({ pathname }: AppBottomNavProps) {
  const items = [...mainNav.items, { ...systemNav.items[0], label: 'More', href: '/app/settings', icon: MoreHorizontal }];

  return (
    <nav className="border-t border-border bg-card px-2 py-2 md:hidden">
      <ul className="grid grid-cols-4 gap-1">
        {items.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <li key={item.label}>
              <Link
                href={item.href}
                className={cn(
                  'flex flex-col items-center gap-1 rounded-md px-2 py-2 text-xs',
                  active ? 'bg-secondary text-primary' : 'text-muted-foreground',
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
