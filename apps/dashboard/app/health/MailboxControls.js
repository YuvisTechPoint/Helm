"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LoaderCircle, Pause, Play, Plus } from "lucide-react";
import { apiPost } from "../../lib/api";

export function PauseToggle({ address, paused }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function toggle() {
    setBusy(true);
    setError(null);
    const action = paused ? "resume" : "pause";
    const result = await apiPost(`/acquisition/mailboxes/${encodeURIComponent(address)}/${action}`);
    setBusy(false);
    if (result.error) setError(result.error);
    else router.refresh();
  }

  return (
    <button type="button" className="btn btn-ghost btn-sm" onClick={toggle} disabled={busy} title={error || undefined}>
      {busy ? <LoaderCircle size={14} className="spin" /> : paused ? <Play size={14} /> : <Pause size={14} />}
      {paused ? "Resume" : "Pause"}
    </button>
  );
}

export function AddMailboxForm() {
  const router = useRouter();
  const [address, setAddress] = useState("");
  const [cap, setCap] = useState("30");
  const [warmed, setWarmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);

  async function submit(event) {
    event.preventDefault();
    const value = address.trim().toLowerCase();
    const domain = value.split("@")[1];
    if (!domain) {
      setMessage({ tone: "error", text: "Enter a full mailbox address." });
      return;
    }
    setBusy(true);
    setMessage(null);
    const result = await apiPost("/acquisition/mailboxes", { address: value, domain, daily_cap: Number(cap) || 30, warmed });
    setBusy(false);
    if (result.error) {
      setMessage({ tone: "error", text: result.error });
      return;
    }
    setAddress("");
    setMessage({ tone: "success", text: warmed ? "Mailbox added and ready." : "Mailbox added. It starts sending after a 14-day warm-up." });
    router.refresh();
  }

  return (
    <form onSubmit={submit}>
      <div className="form-grid" style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1fr)" }}>
        <div className="form-field">
          <label htmlFor="mailbox-address">Mailbox address</label>
          <input id="mailbox-address" type="email" value={address} onChange={(event) => setAddress(event.target.value)} placeholder="ava@try-northwind.com" />
        </div>
        <div className="form-field">
          <label htmlFor="mailbox-cap">Daily cap</label>
          <input id="mailbox-cap" type="number" min={1} max={200} value={cap} onChange={(event) => setCap(event.target.value)} />
        </div>
      </div>
      <label className="checkbox-field" style={{ marginTop: 12 }}>
        <input type="checkbox" checked={warmed} onChange={(event) => setWarmed(event.target.checked)} />
        Already warmed up (skip the 14-day ramp)
      </label>
      <p className="form-hint">Use a secondary domain. The primary business domain is rejected to protect its reputation.</p>
      <div className="form-actions" style={{ marginTop: 12 }}>
        <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !address.trim()}>
          {busy ? <LoaderCircle size={14} className="spin" /> : <Plus size={14} />}
          Add mailbox
        </button>
      </div>
      {message ? <div className={`toast toast-${message.tone}`}>{message.text}</div> : null}
    </form>
  );
}
