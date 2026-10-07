"use client";

import { useState } from "react";
import { Ban, Sparkles } from "lucide-react";
import Alert from "../../components/Alert";
import { apiPost } from "../../lib/api";

export default function PivotPanel({ pivot }) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  if (!pivot || pivot.vetoed || pivot.executed) return null;

  async function veto() {
    setLoading(true);
    setError(null);
    const data = await apiPost("/youtube/optimizer/pivot/veto");
    setLoading(false);
    if (data.error) setError(data.error);
    else setMessage("Pivot vetoed. The channel will stay on the current niche.");
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="card-header">
        <h2 className="card-title"><Sparkles size={16} />Niche pivot proposed</h2>
      </div>
      <p className="report-text">
        The diagnostician wants to move from <strong>{pivot.from_slug}</strong> to <strong>{pivot.to_slug}</strong>.
        You have until {pivot.veto_until ? new Date(pivot.veto_until).toLocaleString() : "72h"} to veto.
      </p>
      <button className="action-btn" disabled={loading} onClick={veto}>
        <Ban size={16} />
        {loading ? "Vetoing…" : "Veto pivot"}
      </button>
      {error ? <Alert variant="error">{error}</Alert> : null}
      {message ? <Alert variant="success">{message}</Alert> : null}
    </div>
  );
}
