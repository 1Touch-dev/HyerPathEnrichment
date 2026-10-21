import { NextRequest, NextResponse } from "next/server";
import { forwardBackendSetCookies } from "@/src/lib/forward-backend-cookies";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const cookie = request.headers.get("cookie");
    if (cookie) {
      headers.cookie = cookie;
    }

    const response = await fetch(`${process.env.BACKEND_API_URL}/auth/login/mfa`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }

    const nextResponse = NextResponse.json(data);
    forwardBackendSetCookies(response, nextResponse);
    return nextResponse;
  } catch (error) {
    console.error("Login MFA error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
