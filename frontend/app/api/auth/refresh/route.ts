import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { forwardBackendSetCookies } from "@/src/lib/forward-backend-cookies";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("refresh_token");

  if (!refreshToken) {
    return NextResponse.json({ error: "No refresh token" }, { status: 401 });
  }

  try {
    const response = await fetch(`${process.env.BACKEND_API_URL}/auth/refresh`, {
      method: "POST",
      headers: {
        Cookie: `refresh_token=${refreshToken.value}`,
      },
    });

    if (!response.ok) {
      return NextResponse.json({ error: "Failed to refresh token" }, { status: response.status });
    }

    const data = await response.json();
    const nextResponse = NextResponse.json(data);
    forwardBackendSetCookies(response, nextResponse);
    return nextResponse;
  } catch (error) {
    console.error("Refresh error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
