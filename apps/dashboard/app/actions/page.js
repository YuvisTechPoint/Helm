"use client";

import { useState } from "react";
import {
  CalendarClock,
  ChevronRight,
  Clapperboard,
  Radar,
  Rocket,
  Target,
  Terminal,
  Timer,
  Users,
  Workflow,
  X,
  Zap,
  LoaderCircle,
  Repeat,
} from "lucide-react";
import Alert from "../../components/Alert";
import PageHeader from "../../components/PageHeader";
import { apiOk, apiPost } from "../../lib/api";

const ACTIONS = [
  {
    group: "Full pipeline",
    items: [
      { path: "/autopilot/daily", label: "Autopilot daily", desc: "Both engines: plan, metrics, source, sequences, sweep.", icon: Rocket, tone: "accent" },
      { path: "/e2e/run", label: "Run both engines", desc: "YouTube cycle and acquisition demo, end to end.", icon: Rocket, tone: "accent" },
      { path: "/autopilot/bootstrap", label: "Bootstrap all schedules", desc: "Register YouTube and acquisition Temporal crons.", icon: CalendarClock, tone: "neutral" },
      { path: "/youtube/cycle", label: "YouTube cycle", desc: "Plan, dry-run, produce, collect metrics, optimise.", icon: Repeat, tone: "info" },
      { path: "/acquisition/demo", label: "Acquisition demo", desc: "Source, outreach, reply, qualify, convert, hand off.", icon: Zap, tone: "success" },
    ],
  },
  {
    group: "YouTube",
    items: [
      { path: "/youtube/workflows/dry-run", label: "Dry-run workflow", desc: "Temporal: 10-topic private upload test.", icon: Workflow, tone: "info" },
      { path: "/youtube/discover", label: "Discover competitors", desc: "Keyword search and channel snapshots.", icon: Radar, tone: "info" },
      { path: "/youtube/workflows/weekly-plan", label: "Weekly plan", desc: "Niche scout plus topic calendar.", icon: CalendarClock, tone: "accent" },
      { path: "/youtube/dry-run", label: "Private dry-run", desc: "Ten-topic private upload gate.", icon: Workflow, tone: "info" },
      { path: "/youtube/schedules/bootstrap", label: "Bootstrap schedules", desc: "Register weekly plan and metrics crons.", icon: CalendarClock, tone: "neutral" },
    ],
  },
  {
    group: "Acquisition",
    items: [
      { path: "/acquisition/icp/generate", label: "Generate ICP cells", desc: "3–5 hypotheses with bandit allocation.", icon: Target, tone: "warning" },
      { path: "/acquisition/leads/source-batch", label: "Source leads", desc: "Pull a batch into the winning ICP cell.", icon: Users, tone: "success" },
      { path: "/acquisition/daily/run", label: "Daily run", desc: "Source to the weekly target and start sequences.", icon: Rocket, tone: "accent" },
      { path: "/acquisition/sweep", label: "Run timers", desc: "Due calls, reminders, re-contacts, and SLA checks.", icon: Timer, tone: "info" },
      { path: "/acquisition/learning/run", label: "Weekly learning", desc: "Retrain scores, promote experiments, reallocate ICP.", icon: Target, tone: "warning" },
      { path: "/acquisition/reports/monthly", label: "Monthly report", desc: "Plain-language owner report.", icon: CalendarClock, tone: "neutral" },
      { path: "/acquisition/prompts/activate", label: "Activate reply prompt", desc: "Eval-gated prompt promotion.", icon: Zap, tone: "success" },
      { path: "/acquisition/sample-email", label: "Sample first-touch", desc: "Critic-checked outreach copy.", icon: Users, tone: "info" },
      { path: "/acquisition/schedules/bootstrap", label: "Bootstrap schedules", desc: "Register daily, sweep, weekly, and monthly crons.", icon: CalendarClock, tone: "neutral" },
    ],
  },
];

const ICON_FOR_GROUP = { "Full pipeline": Rocket, YouTube: Clapperboard, Acquisition: Target };

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
        title="Run engines"
        description="Trigger pipelines on demand. Temporal workflows run when the worker is up; otherwise the API executes synchronously."
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
