"use client";

import { useState } from "react";
import {
  CalendarClock,
  ChevronRight,
  Clapperboard,
  Radar,
  Rocket,
  Terminal,
  Workflow,
  X,
  LoaderCircle,
  Repeat,
} from "lucide-react";
import Alert from "../../components/Alert";
import PageHeader from "../../components/PageHeader";
import { apiOk, apiPost } from "../../lib/api";

const ACTIONS = [
  {
    group: "Pipeline",
    items: [
      { path: "/autopilot/daily", label: "Autopilot daily", desc: "Weekly plan, metrics collection, optional production cycle.", icon: Rocket, tone: "accent" },
      { path: "/e2e/run", label: "Run full cycle", desc: "Plan, dry-run, produce, metrics, and optimize.", icon: Rocket, tone: "accent" },
      { path: "/autopilot/bootstrap", label: "Bootstrap schedules", desc: "Register YouTube Temporal crons.", icon: CalendarClock, tone: "neutral" },
      { path: "/youtube/cycle", label: "YouTube cycle", desc: "Plan, dry-run, produce, collect metrics, optimise.", icon: Repeat, tone: "info" },
    ],
  },
  {
    group: "Workflows",
    items: [
      { path: "/youtube/workflows/dry-run", label: "Dry-run workflow", desc: "Temporal: 10-topic private upload test.", icon: Workflow, tone: "info" },
      { path: "/youtube/discover", label: "Discover competitors", desc: "Keyword search and channel snapshots.", icon: Radar, tone: "info" },
      { path: "/youtube/workflows/weekly-plan", label: "Weekly plan", desc: "Niche scout plus topic calendar.", icon: CalendarClock, tone: "accent" },
      { path: "/youtube/dry-run", label: "Private dry-run", desc: "Ten-topic private upload gate.", icon: Workflow, tone: "info" },
      { path: "/youtube/schedules/bootstrap", label: "Bootstrap schedules", desc: "Register weekly plan and metrics crons.", icon: CalendarClock, tone: "neutral" },
    ],
  },
];

const ICON_FOR_GROUP = { Pipeline: Rocket, Workflows: Clapperboard };

export default function ActionsPage() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(null);
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
    <>
      <PageHeader
        title="Run pipeline"
        description="Trigger YouTube workflows on demand. Temporal runs when the worker is up; otherwise the API executes synchronously."
      />

      {error ? <Alert variant="error">{error}</Alert> : null}

      {ACTIONS.map((group) => {
        const GroupIcon = ICON_FOR_GROUP[group.group];
        return (
          <section key={group.group} style={{ marginBottom: 28 }}>
            <h2 className="section-title">
              <GroupIcon size={13} strokeWidth={2.2} />
              {group.group}
            </h2>
            <div className="action-grid">
              {group.items.map((item) => {
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
                      <p>{running ? "Running…" : item.desc}</p>
                    </span>
                    <ChevronRight size={16} className="action-go" />
                  </button>
                );
              })}
            </div>
          </section>
        );
      })}

      {result ? (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">
              <Terminal size={16} />
              Result <code>{result.path}</code>
            </h2>
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
    </>
  );
}
