import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const authToken = cookieStore.get("auth_token");

  if (!authToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const response = await fetch(`${process.env.BACKEND_API_URL}/auth/delete-account`, {
    method: "POST",
    headers: {
      Cookie: `auth_token=${authToken.value}`,
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
  nextResponse.cookies.delete("auth_token");
  nextResponse.cookies.delete("refresh_token");

  return nextResponse;
}
