"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Globe2, Mail, MessageCircle, MessageSquareText, Phone, Power, Target } from "lucide-react";
import Badge from "../../components/Badge";
import { apiPost } from "../../lib/api";

const CHANNEL_META = {
  email: { label: "Email", icon: Mail, desc: "Cold outreach and replies from secondary mailboxes." },
  whatsapp: { label: "WhatsApp", icon: MessageCircle, desc: "Only for leads who asked to switch or wrote in first." },
  sms: { label: "SMS", icon: MessageSquareText, desc: "Consent-only; STOP withdraws every channel." },
  voice: { label: "AI voice", icon: Phone, desc: "Requested calls only, with an AI disclosure up front." },
};

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

export default function KillSwitchPanel({ controls }) {
  const router = useRouter();
  const [state, setState] = useState(controls);
  const [busy, setBusy] = useState(null);
  const [reason, setReason] = useState(controls.reason || "");
  const [error, setError] = useState(null);

  async function flip(scope, active, channel) {
    const key = channel ? `channel:${channel}` : scope;
    setBusy(key);
    setError(null);
    const result = await apiPost("/acquisition/controls/kill", { scope, active, channel, reason: active ? reason || "paused by owner" : "" });
    setBusy(null);
    if (result.error) {
      setError(result.error);
      return;
    }
    setState((prev) =>
      channel ? { ...prev, channels: { ...prev.channels, [channel]: active } } : { ...prev, [scope]: active },
    );
    router.refresh();
  }

  const engineRows = [
    { scope: "global", label: "Global stop", icon: Globe2, desc: "Halts every automated action across both engines." },
    { scope: "acquisition", label: "Acquisition engine", icon: Power, desc: "Stops sourcing, sequences, replies, and calls." },
    { scope: "tenant", label: "This business", icon: Target, desc: "Pauses all outreach for the current tenant only." },
  ];

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title"><Power size={16} />Kill switches</h2>
        <Badge variant={state.global || state.acquisition || state.tenant ? "danger" : "success"} dot>
          {state.global || state.acquisition || state.tenant ? "Halted" : "Running"}
        </Badge>
      </div>

      <div className="form-field" style={{ marginBottom: 16 }}>
        <label htmlFor="kill-reason">Reason (recorded in the audit log)</label>
        <input id="kill-reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="e.g. Reviewing copy before relaunch" />
      </div>

      {engineRows.map((row) => {
        const Icon = row.icon;
        return (
          <div key={row.scope} className="control-row">
            <div className="control-main">
              <span className={`stat-icon tone-${state[row.scope] ? "danger" : "neutral"}`}><Icon size={15} /></span>
              <div>
                <h4>{row.label}</h4>
                <p>{row.desc}</p>
              </div>
            </div>
            <Toggle label={`Stop ${row.label}`} active={Boolean(state[row.scope])} busy={busy === row.scope} onChange={(next) => flip(row.scope, next)} />
          </div>
        );
      })}

      <h3 className="section-title" style={{ marginTop: 20 }}>Per channel</h3>
      {Object.entries(CHANNEL_META).map(([name, meta]) => {
        const Icon = meta.icon;
        const active = Boolean(state.channels?.[name]);
        return (
          <div key={name} className="control-row">
            <div className="control-main">
              <span className={`stat-icon tone-${active ? "danger" : "neutral"}`}><Icon size={15} /></span>
              <div>
                <h4>{meta.label}</h4>
                <p>{meta.desc}</p>
              </div>
            </div>
            <Toggle label={`Stop ${meta.label}`} active={active} busy={busy === `channel:${name}`} onChange={(next) => flip("channel", next, name)} />
          </div>
        );
      })}

      {error ? <div className="toast toast-error">{error}</div> : null}
    </div>
  );
}
