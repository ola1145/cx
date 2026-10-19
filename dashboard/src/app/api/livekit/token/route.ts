import { NextRequest, NextResponse } from "next/server";

const LIVEKIT_SERVICE = process.env.LIVEKIT_SERVICE_URL ?? "http://localhost:8002";

export async function POST(request: NextRequest) {
  const { room_name } = await request.json();
  const tenantId = request.cookies.get("tenant_id")?.value ?? "dashboard-user";

  const res = await fetch(`${LIVEKIT_SERVICE}/rooms/${room_name}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      room_name,
      participant_name: "Owner",
      participant_identity: tenantId,
      grants: { canPublish: true, canSubscribe: true },
    }),
  });
  if (!res.ok) return NextResponse.json({ error: "Token failed" }, { status: 500 });
  return NextResponse.json(await res.json());
}
