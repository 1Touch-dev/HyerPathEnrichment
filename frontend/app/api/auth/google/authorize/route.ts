import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  // Redirect to backend Google OAuth authorize endpoint
  const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8000";
  const authorizeUrl = `${backendUrl}/auth/google/authorize`;

  return NextResponse.redirect(authorizeUrl);
}
