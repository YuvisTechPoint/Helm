"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

export default function ApiStatus() {
  const [online, setOnline] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const check = () =>
      fetch(`${API_BASE}/health`, { cache: "no-store" })
        .then((r) => !cancelled && setOnline(r.ok))
        .catch(() => !cancelled && setOnline(false));
    check();
    const timer = setInterval(check, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const label = online === null ? "Checking API" : online ? "API online" : "API offline";

  return (
    <span className="status-pill" role="status">
      <span className={`status-dot ${online === null ? "" : online ? "online" : "offline"}`} />
      {label}
    </span>
  );
}
