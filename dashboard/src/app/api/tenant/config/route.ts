import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ADMIN_API_URL ?? "http://localhost:8001";

export async function PATCH(request: NextRequest) {
  const tenantId = request.cookies.get("tenant_id")?.value;
  if (!tenantId) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

  const body = await request.json();
  const res = await fetch(`${API_BASE}/tenants/${tenantId}/config`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.ADMIN_TOKEN ?? ""}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) return NextResponse.json({ error: "Update failed" }, { status: 500 });
  return NextResponse.json(await res.json());
}
