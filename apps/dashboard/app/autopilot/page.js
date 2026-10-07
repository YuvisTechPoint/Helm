import {
  Building2,
  CircleCheck,
  Gauge,
  MonitorPlay,
  Power,
  Radar,
  TriangleAlert,
  Users,
} from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import PageHeader from "../../components/PageHeader";
import RefreshLink from "../../components/RefreshLink";
import StatCard from "../../components/StatCard";
import { apiGet, formatNumber } from "../../lib/api";
import PivotNotice from "../../components/PivotNotice";
import AutopilotActions from "./AutopilotActions";

export default async function AutopilotPage() {
  const status = await apiGet("/autopilot/status");
  const yt = status.youtube || {};
  const acq = status.acquisition || {};
  const funnel = acq.funnel || {};

  return (
    <>
      <PageHeader
        title="Business autopilot"
        description="Both engines in one view. Daily runs plan content, source leads, run sequences, collect metrics, and escalate only on exceptions."
      >
        <RefreshLink />
      </PageHeader>

      {status.error ? <Alert variant="error">{status.error}</Alert> : null}

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <StatCard
          icon={Radar}
          tone={status.ready ? "success" : "warning"}
          label="Autopilot"
          value={status.ready ? "Ready" : "Degraded"}
          hint={status.at ? new Date(status.at).toLocaleString() : "—"}
        />
        <StatCard icon={MonitorPlay} tone="info" label="YouTube uploads" value={formatNumber(yt.uploads)} hint="Private until audit" />
        <StatCard icon={Users} tone="accent" label="Leads sourced" value={formatNumber(funnel.sourced)} hint="Acquisition funnel" />
        <StatCard icon={Building2} tone="success" label="Converted" value={formatNumber(funnel.converted)} hint="Handed to human" />
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-header">
            <h2 className="card-title"><MonitorPlay size={16} />YouTube engine</h2>
            <Badge variant={yt.kill_switch ? "danger" : "success"} dot>{yt.kill_switch ? "Paused" : "Running"}</Badge>
          </div>
          <div className="kv-list">
            <div className="kv-row">
              <span className="kv-key"><Gauge size={15} />Quota remaining</span>
              <span className="kv-val">{formatNumber(yt.quota_remaining)}</span>
            </div>
            <div className="kv-row">
              <span className="kv-key"><TriangleAlert size={15} />Exceptions</span>
              <span className="kv-val">{yt.open_exceptions || 0}</span>
            </div>
            <div className="kv-row">
              <span className="kv-key"><Power size={15} />Audit</span>
              <span className="kv-val">{yt.audit_approved ? "Approved" : "Private only"}</span>
            </div>
          </div>
          <PivotNotice pivot={yt.pivot} variant="compact" />
        </div>

        <div className="card">
          <div className="card-header">
            <h2 className="card-title"><Users size={16} />Acquisition engine</h2>
            <Badge variant={acq.kill_switch ? "danger" : "success"} dot>{acq.kill_switch ? "Paused" : "Running"}</Badge>
          </div>
          <div className="kv-list">
            <div className="kv-row"><span className="kv-key">Profile</span><span className="kv-val">{acq.profile_approved ? "Approved" : "Needs approval"}</span></div>
            <div className="kv-row"><span className="kv-key">Contacted</span><span className="kv-val">{formatNumber(funnel.contacted)}</span></div>
            <div className="kv-row"><span className="kv-key">Replied</span><span className="kv-val">{formatNumber(funnel.replied)}</span></div>
            <div className="kv-row"><span className="kv-key">Qualified</span><span className="kv-val">{formatNumber(funnel.qualified)}</span></div>
            <div className="kv-row"><span className="kv-key">Escalations</span><span className="kv-val">{acq.open_escalations || 0}</span></div>
          </div>
        </div>
      </div>

      <AutopilotActions />

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <h2 className="card-title"><CircleCheck size={16} />What runs unattended</h2>
        </div>
        <ul className="report-text">
          <li>YouTube: weekly plan → research → script → quality gate → render → private publish → analytics → one-change optimise.</li>
          <li>Acquisition: ICP bandit sourcing → score → 4-touch email sequence → reply → qualify → close → CRM handoff.</li>
          <li>Humans only: API audit, policy strikes, legal escalations, niche pivot veto, post-conversion delivery.</li>
        </ul>
      </div>
    </>
  );
}
