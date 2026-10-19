"use client";

import useSWR from "swr";
import { useState } from "react";
import { Save, AlertCircle, CheckCircle } from "lucide-react";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function SettingsPage() {
  const { data: tenant, mutate } = useSWR("/api/tenant/me", fetcher);
  const config = tenant?.config ?? {};

  const [greeting, setGreeting] = useState(config.greeting ?? "");
  const [tone, setTone] = useState(config.tone ?? "professional");
  const [timezone, setTimezone] = useState(config.timezone ?? "America/New_York");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<"idle" | "saved" | "error">("idle");

  async function save() {
    setSaving(true);
    setStatus("idle");
    try {
      const res = await fetch("/api/tenant/config", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ greeting, tone, timezone }),
      });
      if (!res.ok) throw new Error(await res.text());
      await mutate();
      setStatus("saved");
    } catch {
      setStatus("error");
    } finally {
      setSaving(false);
      setTimeout(() => setStatus("idle"), 3000);
    }
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      <div className="space-y-6">
        {/* Greeting */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-1">Agent Greeting</h2>
          <p className="text-xs text-gray-500 mb-3">
            Must include AI disclosure and recording notice.
          </p>
          <textarea
            value={greeting}
            onChange={(e) => setGreeting(e.target.value)}
            rows={4}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            placeholder="Hi, thanks for calling [Business]. This is an AI assistant…"
          />
          {greeting && !greeting.toLowerCase().includes("ai") && (
            <p className="text-xs text-amber-600 flex items-center gap-1 mt-1">
              <AlertCircle size={12} /> Greeting should mention "AI assistant"
            </p>
          )}
        </div>

        {/* Tone */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-3">Agent Tone</h2>
          <div className="grid grid-cols-2 gap-2">
            {(["professional", "friendly", "casual", "formal"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTone(t)}
                className={`px-4 py-2.5 rounded-lg text-sm font-medium capitalize transition-colors border ${
                  tone === t
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Timezone */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-3">Timezone</h2>
          <select
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="America/New_York">Eastern (ET)</option>
            <option value="America/Chicago">Central (CT)</option>
            <option value="America/Denver">Mountain (MT)</option>
            <option value="America/Los_Angeles">Pacific (PT)</option>
            <option value="America/Phoenix">Arizona (no DST)</option>
            <option value="America/Anchorage">Alaska (AKT)</option>
            <option value="Pacific/Honolulu">Hawaii (HT)</option>
          </select>
        </div>

        {/* Save button */}
        <div className="flex items-center gap-3">
          <button
            onClick={save}
            disabled={saving}
            className="flex items-center gap-2 bg-blue-600 text-white rounded-lg px-5 py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <Save size={14} />
            {saving ? "Saving…" : "Save changes"}
          </button>
          {status === "saved" && (
            <span className="flex items-center gap-1 text-sm text-green-600">
              <CheckCircle size={14} /> Saved
            </span>
          )}
          {status === "error" && (
            <span className="flex items-center gap-1 text-sm text-red-600">
              <AlertCircle size={14} /> Save failed
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
