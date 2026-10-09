"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { MonitorPlay, Power } from "lucide-react";
import Badge from "../../components/Badge";
import { apiPost } from "../../lib/api";

function Toggle({ active, busy, onChange, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={active}
      aria-label={label}
      className="switch"
      disabled={busy}
      onClick={() => onChange(!active)}
    />
  );
}

export default function KillSwitchPanel({ initialActive, initialReason }) {
  const router = useRouter();
  const [active, setActive] = useState(initialActive);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState(initialReason || "");
  const [error, setError] = useState(null);

  async function flip(next) {
    setBusy(true);
    setError(null);
    const result = await apiPost(`/youtube/kill-switch?active=${next}&reason=${encodeURIComponent(next ? reason || "paused by owner" : "")}`);
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setActive(Boolean(result.active));
    router.refresh();
  }

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title"><Power size={16} />Kill switch</h2>
        <Badge variant={active ? "danger" : "success"} dot>
          {active ? "Paused" : "Running"}
        </Badge>
      </div>

      <div className="form-field" style={{ marginBottom: 16 }}>
        <label htmlFor="kill-reason">Reason (recorded in the audit log)</label>
        <input id="kill-reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="e.g. Reviewing content before relaunch" />
      </div>

      <div className="control-row">
        <div className="control-main">
          <span className={`stat-icon tone-${active ? "danger" : "neutral"}`}><MonitorPlay size={15} /></span>
          <div>
            <h4>YouTube engine</h4>
            <p>Stops all automated planning, rendering, and publishing.</p>
          </div>
        </div>
        <Toggle label="Stop YouTube engine" active={active} busy={busy} onChange={flip} />
      </div>

      {error ? <div className="toast toast-error">{error}</div> : null}
    </div>
  );
}
