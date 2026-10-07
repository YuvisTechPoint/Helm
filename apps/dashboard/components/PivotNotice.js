"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Ban, Sparkles } from "lucide-react";
import Alert from "./Alert";
import { apiOk, apiPost } from "../lib/api";
import { formatSlug } from "../lib/format";

export default function PivotNotice({ pivot, variant = "compact" }) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  if (!pivot || pivot.vetoed || pivot.executed || dismissed) return null;

  const from = formatSlug(pivot.from_slug);
  const to = formatSlug(pivot.to_slug);
  const deadline = pivot.veto_until
    ? new Date(pivot.veto_until).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : "72 hours";

  async function veto() {
    setLoading(true);
    setError(null);
    const data = await apiPost("/youtube/optimizer/pivot/veto");
    setLoading(false);
    if (!apiOk(data)) setError(data.error || "Could not veto pivot");
    else {
      setMessage("Pivot vetoed — the channel stays on the current niche.");
      setDismissed(true);
    }
  }

  const body = (
    <>
      <div className="pivot-banner-icon" aria-hidden="true">
        <Sparkles size={17} strokeWidth={2} />
      </div>
      <div className="pivot-banner-body">
        <strong>Niche pivot proposed</strong>
        <p>
          The diagnostician recommends moving from{" "}
          <span className="pivot-slug">{from}</span>
          {" → "}
          <span className="pivot-slug">{to}</span>.
          {variant === "compact" ? (
            <> Auto-applies after the veto window unless you stop it.</>
          ) : (
            <> You can veto until <time>{deadline}</time>.</>
          )}
        </p>
      </div>
      <div className="pivot-banner-actions">
        {variant === "compact" ? (
          <Link href="/youtube" className="btn btn-ghost btn-sm">
            Review
            <ArrowRight size={14} />
          </Link>
        ) : null}
        <button type="button" className="btn btn-secondary btn-sm" disabled={loading} onClick={veto}>
          <Ban size={14} />
          {loading ? "Vetoing…" : "Veto pivot"}
        </button>
      </div>
    </>
  );

  if (variant === "full") {
    return (
      <div className="card pivot-card">
        <div className="pivot-banner pivot-banner-full">{body}</div>
        {error ? <Alert variant="error">{error}</Alert> : null}
        {message ? <Alert variant="success">{message}</Alert> : null}
      </div>
    );
  }

  return (
    <div className="pivot-notice-compact">
      <div className="pivot-banner">{body}</div>
      {error ? <Alert variant="error">{error}</Alert> : null}
      {message ? <Alert variant="success">{message}</Alert> : null}
    </div>
  );
}
