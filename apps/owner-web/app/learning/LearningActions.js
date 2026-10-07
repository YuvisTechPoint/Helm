"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { BrainCircuit, FileText, LoaderCircle, Rocket, Save } from "lucide-react";
import { apiOk, apiPost } from "../../lib/api";

const ACTIONS = [
  { key: "learn", path: "/acquisition/learning/run", label: "Run weekly learning", icon: BrainCircuit, done: "Learning pass complete." },
  { key: "report", path: "/acquisition/reports/monthly", label: "Generate monthly report", icon: FileText, done: "Report generated and sent to the owner." },
  { key: "prompt", path: "/acquisition/prompts/activate", label: "Activate reply prompt", icon: Rocket, done: "Prompt passed the eval gate and is live." },
];

export default function LearningActions({ target }) {
  const router = useRouter();
  const [busy, setBusy] = useState(null);
  const [message, setMessage] = useState(null);
  const [weekly, setWeekly] = useState(String(target ?? 5));

  async function run(action) {
    setBusy(action.key);
    setMessage(null);
    const result = await apiPost(action.path);
    setBusy(null);
    setMessage(!apiOk(result) ? { tone: "error", text: result.error || "Request failed" } : { tone: "success", text: action.done });
    if (!result.error) router.refresh();
  }

  async function saveTarget(event) {
    event.preventDefault();
    const value = Number.parseInt(weekly, 10);
    if (!Number.isFinite(value) || value < 1) {
      setMessage({ tone: "error", text: "Weekly target must be at least 1." });
      return;
    }
    setBusy("volume");
    const result = await apiPost("/acquisition/volume", { weekly_qualified_target: value });
    setBusy(null);
    setMessage(!apiOk(result) ? { tone: "error", text: result.error || "Request failed" } : { tone: "success", text: `Daily plan: ${result.daily_contacts_planned} contacts.` });
    if (!result.error) router.refresh();
  }

  return (
    <div>
      <div className="inline-actions">
        {ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <button key={action.key} type="button" className="btn btn-secondary btn-sm" onClick={() => run(action)} disabled={busy !== null}>
              {busy === action.key ? <LoaderCircle size={14} className="spin" /> : <Icon size={14} />}
              {action.label}
            </button>
          );
        })}
      </div>

      <form className="search-bar" style={{ marginTop: 16, marginBottom: 0 }} onSubmit={saveTarget}>
        <div className="form-field" style={{ flex: 1, margin: 0 }}>
          <label htmlFor="weekly-target">Qualified leads wanted per week</label>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              id="weekly-target"
              type="number"
              min={1}
              max={1000}
              value={weekly}
              onChange={(event) => setWeekly(event.target.value)}
            />
            <button type="submit" className="btn btn-primary btn-sm" style={{ height: 36 }} disabled={busy !== null}>
              {busy === "volume" ? <LoaderCircle size={14} className="spin" /> : <Save size={14} />}
              Save
            </button>
          </div>
        </div>
      </form>

      {message ? <div className={`toast toast-${message.tone}`}>{message.text}</div> : null}
    </div>
  );
}
