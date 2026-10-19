import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ADMIN_API_URL ?? "http://localhost:8001";

export async function GET(request: NextRequest) {
  const tenantId = request.cookies.get("tenant_id")?.value;
  if (!tenantId) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

  const res = await fetch(`${API_BASE}/tenants/${tenantId}`, {
    headers: { Authorization: `Bearer ${process.env.ADMIN_TOKEN ?? ""}` },
  });
  if (!res.ok) return NextResponse.json({ error: "Not found" }, { status: 404 });
  const tenant = await res.json();
  return NextResponse.json({
    status: tenant.billing_status,
    card_last4: tenant.card_last4,
    card_brand: tenant.card_brand,
    trial_end: tenant.trial_end,
    current_period_end: tenant.current_period_end,
  });
}
