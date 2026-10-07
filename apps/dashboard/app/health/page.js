import { Activity, Flame, Inbox, Mail, MailCheck, MailPlus, PauseCircle } from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import EmptyState from "../../components/EmptyState";
import PageHeader from "../../components/PageHeader";
import RefreshLink from "../../components/RefreshLink";
import StatCard from "../../components/StatCard";
import { apiGet } from "../../lib/api";
import { AddMailboxForm, PauseToggle } from "./MailboxControls";

const WARMUP_DAYS = 14;

function warmupDay(started) {
  if (!started) return null;
  const elapsed = Math.floor((Date.now() - new Date(started).getTime()) / 86_400_000);
  return Math.min(WARMUP_DAYS, Math.max(0, elapsed));
}

function mailboxStatus(box) {
  if (box.paused) return { label: "Paused", variant: "warning" };
  if (!box.warmed) return { label: "Warming up", variant: "info" };
  const healthy = box.inbox_rate >= 0.9 && box.bounce_rate < 0.05 && (box.complaint_rate || 0) < 0.001;
  return healthy ? { label: "Healthy", variant: "success" } : { label: "Degraded", variant: "danger" };
}

export default async function HealthPage() {
  const data = await apiGet("/acquisition/mailboxes");
  const rows = data.mailboxes || [];
  const ready = rows.filter((box) => box.ready);
  const sent = rows.reduce((sum, box) => sum + (box.sent_today || 0), 0);
  const cap = ready.reduce((sum, box) => sum + (box.daily_cap || 0), 0);
  const paused = rows.filter((box) => box.paused).length;
  const warming = rows.filter((box) => !box.warmed).length;
  const avgInbox = rows.length ? rows.reduce((sum, box) => sum + (box.inbox_rate || 0), 0) / rows.length : 0;

  return (
    <>
      <PageHeader
        title="Mailbox health"
        description="Sending capacity, warm-up progress, and deliverability for each secondary-domain mailbox. Mailboxes pause automatically on bounce or complaint spikes."
      >
        <RefreshLink />
      </PageHeader>

      {data.error ? <Alert variant="error">{data.error}</Alert> : null}

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <StatCard icon={Mail} tone="accent" label="Ready mailboxes" value={`${ready.length}/${rows.length}`} hint={warming ? `${warming} warming up` : "All warmed"} />
        <StatCard icon={MailCheck} tone="info" label="Sent today" value={`${sent}/${cap}`} hint="Against ready capacity" />
        <StatCard icon={Inbox} tone={avgInbox >= 0.9 ? "success" : "warning"} label="Avg inbox rate" value={`${(avgInbox * 100).toFixed(0)}%`} hint="Target ≥ 90%" />
        <StatCard icon={PauseCircle} tone={paused ? "warning" : "neutral"} label="Paused" value={paused} hint="Bounce ≥ 5% or complaints ≥ 0.1%" />
      </div>

      <div className="grid grid-dash">
        {rows.length === 0 && !data.error ? (
          <div className="card">
            <EmptyState icon={Mail} title="No mailboxes" description="Add a secondary-domain mailbox to start outreach." />
          </div>
        ) : (
          <div className="card card-flush">
            <div className="card-header">
              <h2 className="card-title"><Activity size={16} />Sending mailboxes</h2>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Mailbox</th>
                    <th>Daily usage</th>
                    <th>Inbox</th>
                    <th>Bounce</th>
                    <th>Complaints</th>
                    <th>Status</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((box) => {
                    const utilization = box.daily_cap ? (box.sent_today / box.daily_cap) * 100 : 0;
                    const status = mailboxStatus(box);
                    const day = box.warmed ? null : warmupDay(box.warmup_started);
                    return (
                      <tr key={box.address}>
                        <td>
                          <span className="cell-primary">
                            <span className="stat-icon tone-neutral"><Mail size={14} /></span>
                            <span>
                              {box.address}
                              <div className="cell-muted" style={{ fontSize: 12, fontWeight: 400 }}>{box.domain} · {box.sent_total ?? 0} sent total</div>
                            </span>
                          </span>
                        </td>
                        <td style={{ minWidth: 140 }}>
                          {box.sent_today} / {box.daily_cap}
                          <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${Math.min(utilization, 100)}%` }} />
                          </div>
                        </td>
                        <td>{(box.inbox_rate * 100).toFixed(0)}%</td>
                        <td>{(box.bounce_rate * 100).toFixed(1)}%</td>
                        <td>{((box.complaint_rate || 0) * 100).toFixed(2)}%</td>
                        <td>
                          <Badge variant={status.variant} dot>{status.label}</Badge>
                          {day != null ? (
                            <div className="cell-muted" style={{ fontSize: 12, marginTop: 4 }}>
                              <Flame size={11} style={{ verticalAlign: -1 }} /> Day {day} of {WARMUP_DAYS}
                            </div>
                          ) : null}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <PauseToggle address={box.address} paused={box.paused} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="card">
          <div className="card-header">
            <h2 className="card-title"><MailPlus size={16} />Add mailbox</h2>
          </div>
          <AddMailboxForm />
        </div>
      </div>
    </>
  );
}
