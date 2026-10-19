"use client";

import useSWR from "swr";
import { useState } from "react";
import { Search, RefreshCw } from "lucide-react";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface Tenant {
  tenant_id: string;
  business_name?: string;
  status?: string;
  billing_status?: string;
  e164?: string;
  created_at?: number;
}

const STATUS_COLORS: Record<string, string> = {
  live: "bg-green-100 text-green-700",
  day_one: "bg-blue-100 text-blue-700",
  provisioned: "bg-yellow-100 text-yellow-700",
  lapsed: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-500",
};

export default function TenantsPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading, mutate } = useSWR<{ items: Tenant[] }>(
    "/api/admin/tenants",
    fetcher
  );

  const tenants = (data?.items ?? []).filter((t) =>
    !search ||
    t.business_name?.toLowerCase().includes(search.toLowerCase()) ||
    t.tenant_id.includes(search) ||
    t.e164?.includes(search)
  );

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Tenants</h1>
        <button
          onClick={() => mutate()}
          className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Search by name, ID or number…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Business</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Number</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Billing</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Created</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={5} className="text-center py-12 text-gray-400">Loading…</td>
              </tr>
            )}
            {!isLoading && tenants.length === 0 && (
              <tr>
                <td colSpan={5} className="text-center py-12 text-gray-400">No tenants found</td>
              </tr>
            )}
            {tenants.map((t) => (
              <tr key={t.tenant_id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                <td className="px-5 py-3">
                  <div className="font-medium text-gray-900">{t.business_name ?? "—"}</div>
                  <div className="text-xs text-gray-400 font-mono">{t.tenant_id.slice(0, 8)}…</div>
                </td>
                <td className="px-5 py-3 text-gray-700 font-mono">{t.e164 ?? "—"}</td>
                <td className="px-5 py-3">
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[t.status ?? ""] ?? "bg-gray-100 text-gray-600"}`}>
                    {t.status ?? "—"}
                  </span>
                </td>
                <td className="px-5 py-3 text-gray-600">{t.billing_status ?? "—"}</td>
                <td className="px-5 py-3 text-gray-500">
                  {t.created_at
                    ? new Date(t.created_at * 1000).toLocaleDateString()
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
