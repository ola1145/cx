"use client";

import { useState } from "react";
import { Video, Phone, Mic, MicOff, VideoOff } from "lucide-react";

export default function LiveKitPage() {
  const [roomName, setRoomName] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inRoom, setInRoom] = useState(false);

  async function joinRoom() {
    if (!roomName.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/livekit/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room_name: roomName }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setToken(data.token);
      setInRoom(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to join room");
    } finally {
      setLoading(false);
    }
  }

  if (inRoom && token) {
    return <LiveRoom token={token} roomName={roomName} onLeave={() => { setInRoom(false); setToken(null); }} />;
  }

  return (
    <div className="p-8 max-w-xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Video size={22} /> Live Rooms
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Join or monitor a LiveKit room for a tenant session.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">Room name</label>
        <input
          type="text"
          placeholder="e.g. abc12345-voice-1729377600"
          value={roomName}
          onChange={(e) => setRoomName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && joinRoom()}
          className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
        />
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        <button
          onClick={joinRoom}
          disabled={loading || !roomName.trim()}
          className="w-full bg-blue-600 text-white rounded-lg px-4 py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Joining…" : "Join Room"}
        </button>
      </div>
    </div>
  );
}

function LiveRoom({
  token,
  roomName,
  onLeave,
}: {
  token: string;
  roomName: string;
  onLeave: () => void;
}) {
  const [muted, setMuted] = useState(false);
  const [videoOff, setVideoOff] = useState(false);

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Live: {roomName}</h1>
          <p className="text-xs text-gray-400 font-mono mt-0.5">{token.slice(0, 40)}…</p>
        </div>
        <button
          onClick={onLeave}
          className="flex items-center gap-2 bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
        >
          <Phone size={14} className="rotate-[135deg]" /> Leave
        </button>
      </div>

      {/* Embed LiveKit components */}
      <div className="bg-gray-900 rounded-xl aspect-video flex items-center justify-center text-gray-500 text-sm mb-4">
        <div className="text-center">
          <Video size={36} className="mx-auto mb-2 opacity-40" />
          <p>LiveKit room active</p>
          <p className="text-xs mt-1 opacity-60">Install @livekit/components-react for full UI</p>
        </div>
      </div>

      <div className="flex gap-3 justify-center">
        <button
          onClick={() => setMuted(!muted)}
          className={`p-3 rounded-full border transition-colors ${muted ? "bg-red-100 border-red-200 text-red-600" : "bg-white border-gray-200 text-gray-700 hover:bg-gray-50"}`}
        >
          {muted ? <MicOff size={18} /> : <Mic size={18} />}
        </button>
        <button
          onClick={() => setVideoOff(!videoOff)}
          className={`p-3 rounded-full border transition-colors ${videoOff ? "bg-red-100 border-red-200 text-red-600" : "bg-white border-gray-200 text-gray-700 hover:bg-gray-50"}`}
        >
          {videoOff ? <VideoOff size={18} /> : <Video size={18} />}
        </button>
      </div>
    </div>
  );
}
