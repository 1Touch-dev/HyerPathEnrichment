import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  // Backend uses "access_token" not "auth_token"
  const authToken = cookieStore.get("access_token");

  if (!authToken) {
    return NextResponse.json({ message: "Not authenticated" }, { status: 200 });
  }

  try {
    const response = await fetch(`${process.env.BACKEND_API_URL}/auth/logout`, {
      method: "POST",
      headers: {
        Cookie: `access_token=${authToken.value}`,
      },
    });

    // Clear cookies regardless of backend response
    const nextResponse = NextResponse.json({ message: "Logged out successfully" });
    nextResponse.cookies.delete("access_token");
    nextResponse.cookies.delete("refresh_token");

    return nextResponse;
  } catch (error) {
    console.error("Logout error:", error);

    // Still clear cookies even if backend fails
    const nextResponse = NextResponse.json({ message: "Logged out successfully" });
    nextResponse.cookies.delete("access_token");
    nextResponse.cookies.delete("refresh_token");

    return nextResponse;
  }
}
