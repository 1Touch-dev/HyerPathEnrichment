import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { parseResponseEnvelopeError, unwrapEnvelopeData } from "@/src/lib/api-envelope";
import { backendFetchPublic } from "@/src/lib/backend-client";

type PublicStaffInvite = {
  invited_by_name: string | null;
  role_name: string;
  email: string;
  expires_at: string;
};

/**
 * Server component for the public invite-preview link an invited staff member
 * receives. Reads GET /api/staff-invites/{token} through the public BFF proxy
 * at frontend/app/api/staff-invites/[token]/route.ts, which forwards the
 * backend's `staff_invites/router.py::get_invite` 404 (unknown token) / 410
 * (already accepted or expired) responses.
 */
export default async function InviteTokenPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;

  let response: Response;
  try {
    response = await backendFetchPublic(`/api/staff-invites/${token}`);
  } catch {
    return (
      <InviteUnavailableCard message="We couldn't reach the server to load this invite. Please try again shortly." />
    );
  }

  if (response.status === 404) {
    notFound();
  }

  if (response.status === 410) {
    const apiError = await parseResponseEnvelopeError(response);
    return <InviteUnavailableCard message={apiError.message} />;
  }

  if (!response.ok) {
    return <InviteUnavailableCard message="Something went wrong loading this invite." />;
  }

  const raw = await response.json();
  const invite = unwrapEnvelopeData<PublicStaffInvite>(raw);

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <Card className="w-full max-w-md p-8 shadow-lg text-center">
        <h1 className="text-2xl font-bold tracking-tight">You&apos;re invited</h1>
        <p className="text-muted-foreground mt-2">
          {invite.invited_by_name ? `${invite.invited_by_name} invited you` : "You've been invited"}{" "}
          to join as a <span className="font-semibold">{invite.role_name}</span>.
        </p>
        <p className="text-sm text-muted-foreground mt-4">
          This invite is for <span className="font-medium">{invite.email}</span> and expires{" "}
          {new Date(invite.expires_at).toLocaleString()}.
        </p>
        <Button asChild className="w-full mt-6">
          <Link href={`/register?invite_token=${encodeURIComponent(token)}`}>Accept invite</Link>
        </Button>
      </Card>
    </div>
  );
}

function InviteUnavailableCard({ message }: { message: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <Card className="w-full max-w-md p-8 shadow-lg text-center">
        <h1 className="text-2xl font-bold tracking-tight">Invite unavailable</h1>
        <p className="text-muted-foreground mt-2">{message}</p>
        <Button asChild variant="outline" className="w-full mt-6">
          <Link href="/register">Go to sign up</Link>
        </Button>
      </Card>
    </div>
  );
}
