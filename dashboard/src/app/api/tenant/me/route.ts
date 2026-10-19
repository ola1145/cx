import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ADMIN_API_URL ?? "http://localhost:8001";

// GET /api/tenant/me  -- returns the current tenant from session cookie
export async function GET(request: NextRequest) {
  const tenantId = request.cookies.get("tenant_id")?.value;
  if (!tenantId) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }
  const res = await fetch(`${API_BASE}/tenants/${tenantId}`, {
    headers: { Authorization: `Bearer ${process.env.ADMIN_TOKEN ?? ""}` },
  });
  if (!res.ok) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json(await res.json());
}
