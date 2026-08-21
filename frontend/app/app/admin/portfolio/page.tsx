import { PortfolioModerationPanel } from "@/features/admin";

export default function AdminPortfolioPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Portfolio moderation</h1>
      <PortfolioModerationPanel />
    </div>
  );
}
