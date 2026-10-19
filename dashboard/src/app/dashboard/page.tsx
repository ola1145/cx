"use client";

import useSWR from "swr";
import { Phone, Users, Clock, TrendingUp, AlertCircle } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const fetcher = (url: string) =>
  fetch(url).then((r) => {
    if (!r.ok) throw new Error("API error");
    return r.json();
  });

interface Stat {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}

function StatCard({ label, value, icon, color }: Stat) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 flex items-center gap-4">
      <div className={`p-3 rounded-lg ${color}`}>{icon}</div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-2xl font-semibold text-gray-900">{value}</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: tenant, error: tenantError } = useSWR("/api/tenant/me", fetcher);
  const { data: metrics } = useSWR("/api/metrics", fetcher, {
    refreshInterval: 30_000,
  });

  if (tenantError) {
    return (
      <div className="flex items-center gap-2 p-8 text-red-600">
        <AlertCircle size={20} />
        <span>Failed to load tenant. Please refresh.</span>
      </div>
    );
  }

  const stats: Stat[] = [
    {
      label: "Business Phone",
      value: tenant?.e164 ?? "Pending",
      icon: <Phone size={20} className="text-blue-600" />,
      color: "bg-blue-50",
    },
    {
      label: "Status",
      value: tenant?.status ?? "—",
      icon: <TrendingUp size={20} className="text-green-600" />,
      color: "bg-green-50",
    },
    {
      label: "Active Calls Today",
      value: metrics?.calls_today ?? 0,
      icon: <Clock size={20} className="text-purple-600" />,
      color: "bg-purple-50",
    },
    {
      label: "Messages Today",
      value: metrics?.messages_today ?? 0,
      icon: <Users size={20} className="text-orange-600" />,
      color: "bg-orange-50",
    },
  ];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          {tenant?.business_name ?? "Loading…"}
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          {tenant?.created_at
            ? `Member since ${formatDistanceToNow(new Date(tenant.created_at * 1000))} ago`
            : ""}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
        {stats.map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today section */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Today</h2>
          <div className="space-y-3">
            {tenant?.hours ? (
              Object.entries(
                (tenant.config?.hours?.days ?? {}) as Record<
                  string,
                  { open: string; close: string; closed: boolean }
                >
              )
                .slice(0, 3)
                .map(([day, h]) => (
                  <div key={day} className="flex justify-between text-sm">
                    <span className="capitalize text-gray-600">{day}</span>
                    <span className="text-gray-800 font-medium">
                      {h.closed ? "Closed" : `${h.open} – ${h.close}`}
                    </span>
                  </div>
                ))
            ) : (
              <p className="text-sm text-gray-400">Hours not yet configured</p>
            )}
          </div>
        </div>

        {/* Quick links */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Quick Actions</h2>
          <div className="space-y-2">
            <a
              href="/dashboard/settings"
              className="block w-full text-left px-4 py-2.5 rounded-lg text-sm text-blue-600 bg-blue-50 hover:bg-blue-100 transition-colors"
            >
              Update business hours & services
            </a>
            <a
              href="/dashboard/livekit"
              className="block w-full text-left px-4 py-2.5 rounded-lg text-sm text-purple-600 bg-purple-50 hover:bg-purple-100 transition-colors"
            >
              Join live call room
            </a>
            <a
              href="/dashboard/billing"
              className="block w-full text-left px-4 py-2.5 rounded-lg text-sm text-green-600 bg-green-50 hover:bg-green-100 transition-colors"
            >
              Billing &amp; subscription
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
