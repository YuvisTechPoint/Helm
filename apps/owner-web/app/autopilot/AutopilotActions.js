"use client";

import { useState } from "react";
import { CalendarClock, Play, Rocket } from "lucide-react";
import Alert from "../../components/Alert";
import { apiOk, apiPost } from "../../lib/api";

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
    else setResult(data);
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="card-header">
        <h2 className="card-title"><Rocket size={16} />Run autopilot</h2>
      </div>
      <div className="action-grid">
        <button className="action-btn" disabled={loading} onClick={() => run("/autopilot/daily")}>
          <Play size={16} />
          {loading === "/autopilot/daily" ? "Running…" : "Daily run (both engines)"}
        </button>
        <button className="action-btn" disabled={loading} onClick={() => run("/autopilot/bootstrap")}>
          <CalendarClock size={16} />
          {loading === "/autopilot/bootstrap" ? "Registering…" : "Bootstrap Temporal schedules"}
        </button>
      </div>
      {error ? <Alert variant="error">{error}</Alert> : null}
      {result ? (
        <pre className="code-block" style={{ marginTop: 12, maxHeight: 320, overflow: "auto" }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
