'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/src/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { toggleSidebar } from '@/store/slices/uiSlice';
import { allNavSections, footerNav } from './nav-config';

export function AppSidebar() {
  const pathname = usePathname();
  const dispatch = useAppDispatch();
  const sidebarOpen = useAppSelector((state) => state.ui.sidebarOpen);

  const isActive = (href: string) => {
    if (href === '/app') return pathname === '/app';
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <aside
      className={cn(
        'flex h-full flex-col border-r border-border bg-card transition-all duration-200',
        sidebarOpen ? 'w-60' : 'w-16',
      )}
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-4">
        {sidebarOpen ? (
          <Link href="/app" className="flex flex-col gap-0.5 px-1">
            <span className="text-xs font-semibold uppercase tracking-widest text-brand-primary">Hyrepath</span>
            <span className="text-[10px] text-muted-foreground">Enrichment Console</span>
          </Link>
        ) : (
          <Link href="/app" className="mx-auto text-xs font-bold text-brand-primary">
            H
          </Link>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={() => dispatch(toggleSidebar())}
          aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
        </Button>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-2 py-4">
        {allNavSections.map((section) => (
          <div key={section.title}>
            {sidebarOpen ? (
              <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                {section.title}
              </p>
            ) : null}
            <ul className="space-y-1">
              {section.items.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        'flex items-center gap-3 rounded-md px-2 py-2 text-sm transition-colors',
                        active
                          ? 'bg-brand-primary/15 text-brand-primary'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                        !sidebarOpen && 'justify-center px-0',
                      )}
                      title={!sidebarOpen ? item.label : undefined}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      {sidebarOpen ? <span>{item.label}</span> : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-border px-2 py-3">
        <ul className="space-y-1">
          {footerNav.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.label}>
                <button
                  type="button"
                  disabled={item.disabled}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-md px-2 py-2 text-sm text-muted-foreground',
                    !sidebarOpen && 'justify-center px-0',
                    item.disabled && 'cursor-not-allowed opacity-50',
                  )}
                  title={!sidebarOpen ? item.label : undefined}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {sidebarOpen ? <span>{item.label}</span> : null}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}
