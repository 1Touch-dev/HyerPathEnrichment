import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const { token } = await request.json();

  const response = await fetch(`${process.env.BACKEND_API_URL}/auth/verify-email?token=${token}`, {
    method: "POST",
  });

  if (!response.ok) {
    const error = await response.json();
    return NextResponse.json(
      { error: error.detail || "Verification failed" },
      { status: response.status },
    );
  }

  return NextResponse.json({ success: true });
}
