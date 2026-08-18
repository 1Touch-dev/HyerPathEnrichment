import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { isMockMode } from "@/src/lib/mocks/enabled";

const MOCK_USER = {
  id: "mock-user-1",
  email: "mock.user@hyrepath.dev",
  first_name: "Mock",
  last_name: "User",
  is_verified: true,
  is_active: true,
  created_at: "2026-01-01T00:00:00.000Z",
};

export async function GET(request: NextRequest) {
  if (isMockMode()) {
    return NextResponse.json(MOCK_USER);
  }

  const cookieStore = await cookies();

  // Backend sets "access_token" not "auth_token"
  const authToken = cookieStore.get("access_token");

  if (!authToken) {
    console.warn("[/api/auth/me] No access_token cookie found");
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  try {
    const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
    const response = await fetch(`${backendUrl}/auth/me`, {
      headers: {
        Cookie: `access_token=${authToken.value}`,
      },
    });

    if (!response.ok) {
      console.warn(`[/api/auth/me] Backend returned ${response.status}`);
      return NextResponse.json({ error: "Failed to fetch user" }, { status: response.status });
    }

    const user = await response.json();
    return NextResponse.json(user);
  } catch (error) {
    console.error("[/api/auth/me] Failed to fetch user:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
