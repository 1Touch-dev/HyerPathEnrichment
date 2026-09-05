import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MfaSetupCard } from "@/features/admin";

export default function OsintSecuritySettingsPage() {
  return (
    <div className="flex flex-col gap-4">
      <Button asChild variant="ghost" className="w-fit">
        <Link href="/osint/settings">
          <ArrowLeft className="mr-2 size-4" />
          Back to Settings
        </Link>
      </Button>
      <h1 className="text-2xl font-semibold tracking-tight">Security</h1>
      <MfaSetupCard />
    </div>
  );
}
