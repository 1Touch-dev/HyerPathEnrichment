import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  // Backend uses "access_token" not "auth_token"
  const authToken = cookieStore.get("access_token");

  if (!authToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const response = await fetch(`${process.env.BACKEND_API_URL}/auth/resend-verification`, {
    method: "POST",
    headers: {
      Cookie: `access_token=${authToken.value}`,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    return NextResponse.json(
      { error: error.detail || "Failed to resend" },
      { status: response.status },
    );
  }

  return NextResponse.json({ success: true });
}
