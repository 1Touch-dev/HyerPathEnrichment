import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const authToken = cookieStore.get("auth_token");

  if (!authToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const response = await fetch(`${process.env.BACKEND_API_URL}/auth/resend-verification`, {
    method: "POST",
    headers: {
      Cookie: `auth_token=${authToken.value}`,
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
