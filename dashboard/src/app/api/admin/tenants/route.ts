import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ADMIN_API_URL ?? "http://localhost:8001";

export async function GET(request: NextRequest) {
  // Proxy to admin console; in production use Cognito JWT from cookie
  const res = await fetch(`${API_BASE}/tenants?limit=100`, {
    headers: {
      Authorization: `Bearer ${process.env.ADMIN_TOKEN ?? ""}`,
    },
  });
  const data = await res.json();
  return NextResponse.json(data);
}
