"use client";

import { useState } from "react";
import { CalendarClock, ChevronRight, LoaderCircle, Play, Rocket, Terminal, X } from "lucide-react";
import Alert from "../../components/Alert";
import { apiOk, apiPost } from "../../lib/api";

const ACTIONS = [
  {
    path: "/autopilot/daily",
    label: "Daily run",
    desc: "Plan content, collect metrics, source leads, run sequences, and sweep timers.",
    icon: Play,
    tone: "accent",
    runningLabel: "Running both engines…",
  },
  {
    path: "/autopilot/bootstrap",
    label: "Bootstrap schedules",
    desc: "Register YouTube and acquisition Temporal crons for unattended operation.",
    icon: CalendarClock,
    tone: "info",
    runningLabel: "Registering schedules…",
  },
];

export default function AutopilotActions() {
  const [loading, setLoading] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function run(path) {
    setLoading(path);
    setError(null);
    setResult(null);
    const data = await apiPost(path);
    setLoading(null);
    if (!apiOk(data)) setError(data.error || "Request failed");
    else setResult({ path, data });
  }

  return (
    <div className="card autopilot-run-card">
      <div className="card-header">
        <h2 className="card-title"><Rocket size={16} />Run autopilot</h2>
      </div>
      <p className="autopilot-run-desc">
        Trigger a full daily cycle on demand. Temporal runs in the background when the worker is up; otherwise the API executes synchronously.
      </p>

      <div className="action-grid">
        {ACTIONS.map((item) => {
          const Icon = item.icon;
          const running = loading === item.path;
          return (
            <button
              key={item.path}
              type="button"
              className={`action-card${running ? " running" : ""}`}
              onClick={() => run(item.path)}
              disabled={loading !== null}
            >
              <span className={`stat-icon tone-${item.tone}`} style={{ width: 36, height: 36, borderRadius: 10 }}>
                {running ? <LoaderCircle size={17} className="spin" /> : <Icon size={17} strokeWidth={2} />}
              </span>
              <span className="action-body">
                <h4>{item.label}</h4>
                <p>{running ? item.runningLabel : item.desc}</p>
              </span>
              <ChevronRight size={16} className="action-go" />
            </button>
          );
        })}
      </div>

      {error ? <Alert variant="error">{error}</Alert> : null}

      {result ? (
        <div className="autopilot-result">
          <div className="autopilot-result-header">
            <span className="autopilot-result-title">
              <Terminal size={15} />
              Result <code>{result.path}</code>
            </span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setResult(null)}>
              <X size={14} />
              Clear
            </button>
          </div>
          <div className="result-panel">
            <pre>{JSON.stringify(result.data, null, 2)}</pre>
          </div>
        </div>
      ) : null}
    </div>
  );
}
