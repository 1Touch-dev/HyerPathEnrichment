'use client';

import { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { AppBottomNav } from './AppBottomNav';
import { AppNavRail } from './AppNavRail';
import { AppSidebar } from './AppSidebar';
import { AppTopbar } from './AppTopbar';

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <div className="hidden lg:flex">
        <AppSidebar />
      </div>
      <AppNavRail pathname={pathname} />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar />
        <main className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">{children}</main>
        <AppBottomNav pathname={pathname} />
      </div>
    </div>
  );
}
