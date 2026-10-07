"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Link2, LoaderCircle, Power } from "lucide-react";
import { apiGet, apiPost } from "../../lib/api";

export function KillSwitchToggle({ active }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function toggle() {
    setBusy(true);
    setError(null);
    const next = !active;
    const reason = next ? "manual pause from dashboard" : "";
    const result = await apiPost(`/youtube/kill-switch?active=${next}&reason=${encodeURIComponent(reason)}`);
    setBusy(false);
    if (result.error) setError(result.error);
    else router.refresh();
  }

  return (
    <button type="button" className={`btn btn-sm ${active ? "btn-danger" : "btn-ghost"}`} onClick={toggle} disabled={busy} title={error || undefined}>
      {busy ? <LoaderCircle size={14} className="spin" /> : <Power size={14} />}
      {active ? "Disable kill switch" : "Activate kill switch"}
    </button>
  );
}

export function ConnectYouTubeButton() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function connect() {
    setBusy(true);
    setError(null);
    const result = await apiGet("/youtube/oauth/start");
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    if (result.url) window.open(result.url, "_blank", "noopener,noreferrer");
  }

  return (
    <button type="button" className="btn btn-primary btn-sm" onClick={connect} disabled={busy}>
      {busy ? <LoaderCircle size={14} className="spin" /> : <Link2 size={14} />}
      Connect YouTube
      {error ? <span className="form-hint" style={{ marginLeft: 8 }}>{error}</span> : null}
    </button>
  );
}
