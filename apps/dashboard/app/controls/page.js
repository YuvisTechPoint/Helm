import { MonitorPlay, ShieldCheck } from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import PageHeader from "../../components/PageHeader";
import RefreshLink from "../../components/RefreshLink";
import { apiGet } from "../../lib/api";
import KillSwitchPanel from "./KillSwitchPanel";

const GUARANTEES = [
  "Synthetic media and AI voice disclosures on every upload",
  "Quality gate blocks publish until script, render, and metadata pass",
  "Kill switch halts all automated publishing instantly",
  "Policy strikes and limited ads trigger automatic pause",
  "Every publish is idempotent and audit-logged",
];

export default async function ControlsPage() {
  const status = await apiGet("/youtube/status");
  const error = status.error;

  return (
    <>
      <PageHeader
        title="Controls & compliance"
        description="Pause the channel engine instantly and review policy guarantees enforced in code."
      >
        <RefreshLink />
      </PageHeader>

      {error ? <Alert variant="error">{error}</Alert> : null}

      <div className="grid grid-dash">
        <div className="stack-16">
          {error ? null : <KillSwitchPanel initialActive={Boolean(status.kill_switch)} initialReason="" />}
        </div>

        <div className="stack-16">
          <div className="card">
            <div className="card-header">
              <h2 className="card-title"><MonitorPlay size={16} />Channel status</h2>
              <Badge variant={status.audit_approved ? "success" : "warning"} dot>
                {status.audit_approved ? "Audit approved" : "Private only"}
              </Badge>
            </div>
            <div className="kv-list">
              <div className="kv-row"><span className="kv-key">Kill switch</span><span className="kv-val">{status.kill_switch ? "Active" : "Off"}</span></div>
              <div className="kv-row"><span className="kv-key">Quota remaining</span><span className="kv-val">{status.quota_remaining ?? "—"}</span></div>
              <div className="kv-row"><span className="kv-key">Open exceptions</span><span className="kv-val">{(status.exceptions || []).length}</span></div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h2 className="card-title"><ShieldCheck size={16} />Enforced in code</h2>
            </div>
            <ul className="report-text">
              {GUARANTEES.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </>
  );
}
