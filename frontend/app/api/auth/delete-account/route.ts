import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  // Backend uses "access_token" not "auth_token"
  const authToken = cookieStore.get("access_token");

  if (!authToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const response = await fetch(`${process.env.BACKEND_API_URL}/auth/delete-account`, {
    method: "POST",
    headers: {
      Cookie: `access_token=${authToken.value}`,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    return NextResponse.json(
      { error: error.detail || "Failed to delete account" },
      { status: response.status },
    );
  }

  // Clear cookies on successful deletion
  const nextResponse = NextResponse.json({ success: true });
  nextResponse.cookies.delete("access_token");
  nextResponse.cookies.delete("refresh_token");

  return nextResponse;
}
