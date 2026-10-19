"use client";

import useSWR from "swr";
import { CreditCard, ExternalLink, AlertTriangle } from "lucide-react";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface Billing {
  status?: string;
  card_last4?: string;
  card_brand?: string;
  trial_end?: number;
  current_period_end?: number;
  portal_url?: string;
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  trialing: { label: "Trial", color: "bg-blue-100 text-blue-700" },
  active: { label: "Active", color: "bg-green-100 text-green-700" },
  past_due: { label: "Past due", color: "bg-amber-100 text-amber-700" },
  lapsed: { label: "Lapsed", color: "bg-red-100 text-red-700" },
  cancelled: { label: "Cancelled", color: "bg-gray-100 text-gray-500" },
};

export default function BillingPage() {
  const { data: billing } = useSWR<Billing>("/api/billing/me", fetcher);

  const status = STATUS_MAP[billing?.status ?? ""] ?? { label: billing?.status ?? "—", color: "bg-gray-100 text-gray-600" };

  async function openPortal() {
    const res = await fetch("/api/billing/portal", { method: "POST" });
    const data = await res.json();
    if (data.url) window.location.href = data.url;
  }

  return (
    <div className="p-8 max-w-xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Billing</h1>

      <div className="space-y-4">
        {/* Status card */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-800">Subscription</h2>
            <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${status.color}`}>
              {status.label}
            </span>
          </div>

          {billing?.status === "past_due" && (
            <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 mb-4">
              <AlertTriangle size={16} className="text-amber-600 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-amber-700">
                Payment is past due. Update your card to avoid service interruption.
              </p>
            </div>
          )}

          {billing?.card_last4 ? (
            <div className="flex items-center gap-3 text-sm text-gray-700 mb-4">
              <CreditCard size={16} className="text-gray-400" />
              <span className="capitalize">{billing.card_brand}</span>
              <span className="font-mono">•••• {billing.card_last4}</span>
            </div>
          ) : (
            <p className="text-sm text-gray-500 mb-4">No card on file</p>
          )}

          {billing?.trial_end && billing.status === "trialing" && (
            <p className="text-xs text-gray-500 mb-4">
              Trial ends {new Date(billing.trial_end * 1000).toLocaleDateString()}
            </p>
          )}

          {billing?.current_period_end && billing.status === "active" && (
            <p className="text-xs text-gray-500 mb-4">
              Next billing date: {new Date(billing.current_period_end * 1000).toLocaleDateString()}
            </p>
          )}

          <button
            onClick={openPortal}
            className="flex items-center gap-2 w-full justify-center bg-gray-900 text-white rounded-lg px-4 py-2.5 text-sm font-medium hover:bg-gray-800 transition-colors"
          >
            <ExternalLink size={14} />
            Manage billing in Stripe
          </button>
        </div>

        <p className="text-xs text-center text-gray-400">
          Your payment is handled securely by Stripe. 1145 AI never stores card details.
        </p>
      </div>
    </div>
  );
}
