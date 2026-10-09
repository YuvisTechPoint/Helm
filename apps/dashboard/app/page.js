import Link from "next/link";
import { Activity, MonitorPlay, Power, ShieldAlert, ShieldCheck, Upload } from "lucide-react";
import Alert from "../components/Alert";
import Badge from "../components/Badge";
import PageHeader from "../components/PageHeader";
import RefreshLink from "../components/RefreshLink";
import StatCard from "../components/StatCard";
import { apiGet, formatNumber } from "../lib/api";

export default async function DashboardPage() {
  const [youtube, health, autopilot] = await Promise.all([
    apiGet("/youtube/status"),
    apiGet("/health"),
    apiGet("/autopilot/status"),
  ]);

  const openEscalations = (youtube.exceptions || []).length;
  const yt = autopilot.youtube || {};

  return (
    <>
      <PageHeader title="Dashboard" description="Live overview of your autonomous YouTube channel engine.">
        <RefreshLink />
      </PageHeader>

      {youtube.error ? <Alert variant="error">{youtube.error}</Alert> : null}

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <StatCard icon={Upload} tone="info" label="Uploads" value={formatNumber(youtube.uploads ?? 0)} hint={`Quota left ${formatNumber(youtube.quota_remaining)}`} />
        <StatCard
          icon={ShieldCheck}
          tone={youtube.audit_approved ? "success" : "warning"}
          label="API audit"
          value={youtube.audit_approved ? "Approved" : "Pending"}
          hint="Required for public uploads"
        />
        <StatCard icon={Activity} tone="accent" label="Autopilot" value={autopilot.mode || "—"} hint={yt.kill_switch ? "Kill switch on" : "Running"} />
        <StatCard
          icon={ShieldAlert}
          tone={openEscalations ? "danger" : "neutral"}
          label="Escalations"
          value={openEscalations}
          hint={openEscalations === 0 ? "Queue clear" : "Needs review"}
        />
      </div>

      <div className="grid grid-dash">
        <div className="card">
          <div className="card-header">
            <h2 className="card-title"><MonitorPlay size={16} />Channel engine</h2>
            <Badge tone={health.status === "ok" ? "success" : "warning"}>{health.status || "unknown"}</Badge>
          </div>
          <div className="kv-grid">
            <div className="kv-row"><span className="kv-key">Niche</span><span className="kv-val">{youtube.niche || "—"}</span></div>
            <div className="kv-row"><span className="kv-key">Dry run</span><span className="kv-val">{youtube.last_dry_run ? `${youtube.last_dry_run.passed} passed` : "Not run"}</span></div>
            <div className="kv-row"><span className="kv-key">Kill switch</span><span className="kv-val">{yt.kill_switch ? "Active" : "Off"}</span></div>
          </div>
          <Link href="/youtube" className="btn btn-secondary" style={{ marginTop: 16 }}>
            Open channel engine
          </Link>
        </div>

        <div className="card">
          <div className="card-header">
            <h2 className="card-title"><Power size={16} />Quick actions</h2>
          </div>
          <div className="stack-12">
            <Link href="/actions" className="btn btn-primary">Run pipeline</Link>
            <Link href="/autopilot" className="btn btn-secondary">Autopilot status</Link>
            <Link href="/escalations" className="btn btn-ghost">View escalations</Link>
          </div>
        </div>
      </div>
    </>
  );
}
