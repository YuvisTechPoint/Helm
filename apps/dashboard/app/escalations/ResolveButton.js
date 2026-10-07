"use client";

import { useState } from "react";
import { Check, LoaderCircle, RotateCcw } from "lucide-react";
import { API_BASE } from "../../lib/api";

export default function ResolveButton({ id, scope }) {
  const [status, setStatus] = useState("idle");

  async function resolve() {
    setStatus("loading");
    const path = scope === "youtube" ? `/youtube/exceptions/${id}/resolve` : `/acquisition/escalations/${id}/resolve`;
    try {
      const response = await fetch(`${API_BASE}${path}`, { method: "POST" });
      setStatus(response.ok ? "done" : "error");
    } catch {
      setStatus("error");
    }
  }

  if (status === "done") {
    return (
      <button type="button" className="btn btn-success btn-sm" disabled>
        <Check size={14} strokeWidth={2.4} />
        Resolved
      </button>
    );
  }

  return (
    <button type="button" className="btn btn-secondary btn-sm" onClick={resolve} disabled={status === "loading"}>
      {status === "loading" ? (
        <LoaderCircle size={14} className="spin" />
      ) : status === "error" ? (
        <RotateCcw size={14} />
      ) : (
        <Check size={14} strokeWidth={2.4} />
      )}
      {status === "loading" ? "Resolving" : status === "error" ? "Retry" : "Resolve"}
    </button>
  );
}
