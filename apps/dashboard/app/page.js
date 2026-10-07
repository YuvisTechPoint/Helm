import Link from "next/link";
import {
  ArrowRight,
  Activity,
  Clock,
  Handshake,
  Mail,
  MonitorPlay,
  Power,
  ShieldAlert,
  ShieldCheck,
  Target,
  Upload,
  Wallet,
} from "lucide-react";
import Alert from "../components/Alert";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";
import FunnelPipeline from "../components/FunnelPipeline";
import PageHeader from "../components/PageHeader";
import RefreshLink from "../components/RefreshLink";
import StatCard from "../components/StatCard";
import { apiGet, formatCents, formatNumber } from "../lib/api";

export default async function DashboardPage() {
  const [funnel, youtube, money, health, escalations] = await Promise.all([
    apiGet("/acquisition/funnel"),
    apiGet("/youtube/status"),
    apiGet("/acquisition/money"),
    apiGet("/acquisition/mailboxes"),
    apiGet("/acquisition/escalations"),
  ]);

  const counts = funnel.counts || {};
  const byIcp = funnel.by_icp || {};
  const converted = counts.converted ?? 0;
  const openEscalations = (escalations.escalations || []).length + (youtube.exceptions || []).length;
  const mailboxes = health.mailboxes || [];

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Live overview of both engines. Escalations are the only queue that needs your attention."
      >
        <RefreshLink />
      </PageHeader>

      {funnel.error ? <Alert variant="error">{funnel.error}</Alert> : null}

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <StatCard icon={Handshake} tone="success" label="Converted clients" value={formatNumber(converted)} hint="Acquisition funnel" />
        <StatCard
          icon={Wallet}
          tone="accent"
          label="Total spend"
          value={formatCents(money.spend_cents)}
          hint={`CPCC ${money.cpcc_cents != null ? formatCents(money.cpcc_cents) : "—"}`}
        />
        <StatCard
          icon={Upload}
          tone="info"
          label="YouTube uploads"
          value={formatNumber(youtube.uploads ?? 0)}
          hint={`Quota left ${formatNumber(youtube.quota_remaining)}`}
        />
        <StatCard
          icon={ShieldAlert}
          tone={openEscalations ? "danger" : "neutral"}
          label="Open escalations"
          value={openEscalations}
          hint={openEscalations === 0 ? "Queue clear" : "Needs review"}
        />
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div>
            <h2 className="card-title"><Target size={16} />Acquisition funnel</h2>
            <p className="card-subtitle">Stage counts with step-to-step conversion.</p>
          </div>
          <Link href="/threads" className="btn btn-ghost btn-sm">
            Conversations <ArrowRight size={14} />
          </Link>
        </div>
        <FunnelPipeline counts={counts} />
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-header">
            <h2 className="card-title"><MonitorPlay size={16} />YouTube engine</h2>
            <Link href="/youtube" className="btn btn-ghost btn-sm">
              Details <ArrowRight size={14} />
            </Link>
          </div>
          <div className="kv-list">
            <div className="kv-row">
              <span className="kv-key"><ShieldCheck size={15} />Audit approved</span>
              <Badge variant={youtube.audit_approved ? "success" : "warning"} dot>
                {youtube.audit_approved ? "Approved" : "Pending"}
              </Badge>
            </div>
            <div className="kv-row">
              <span className="kv-key"><Power size={15} />Kill switch</span>
              <Badge variant={youtube.kill_switch ? "danger" : "success"} dot>
                {youtube.kill_switch ? "Active" : "Off"}
              </Badge>
            </div>
            <div className="kv-row">
              <span className="kv-key"><Clock size={15} />Last dry run</span>
              <span className="kv-val">
                {youtube.last_dry_run ? `${youtube.last_dry_run.passed} passed` : "Not run"}
              </span>
            </div>
          </div>
        </div>

        <div className="card card-flush">
          <div className="card-header">
            <h2 className="card-title"><Activity size={16} />Deliverability health</h2>
            <Link href="/health" className="btn btn-ghost btn-sm">
              Mailboxes <ArrowRight size={14} />
            </Link>
          </div>
          {mailboxes.length === 0 ? (
            <EmptyState icon={Mail} title="No mailboxes configured" description="Add a secondary sending domain to start outreach." />
          ) : (
            mailboxes.map((box) => (
              <div key={box.address} className="list-item">
                <div className="list-item-main">
                  <span className="stat-icon tone-neutral"><Mail size={15} /></span>
                  <div>
                    <h4>{box.address}</h4>
                    <p>
                      {box.sent_today}/{box.daily_cap} sent · inbox {(box.inbox_rate * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>
                <Badge variant={box.paused ? "warning" : "success"} dot>{box.paused ? "Paused" : "Active"}</Badge>
              </div>
            ))
          )}
        </div>
      </div>

      {Object.keys(byIcp).length > 0 ? (
        <div className="card card-flush" style={{ marginTop: 16 }}>
          <div className="card-header">
            <h2 className="card-title"><Target size={16} />Funnel by ICP cell</h2>
            <Link href="/experiments" className="btn btn-ghost btn-sm">
              Experiments <ArrowRight size={14} />
            </Link>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cell</th>
                  <th>Sourced</th>
                  <th>Contacted</th>
                  <th>Replied</th>
                  <th>Positive</th>
                  <th>Qualified</th>
                  <th>Converted</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(byIcp).map(([cell, row]) => (
                  <tr key={cell}>
                    <td><span className="cell-primary">{cell}</span></td>
                    <td>{row.sourced ?? 0}</td>
                    <td>{row.contacted ?? 0}</td>
                    <td>{row.replied ?? 0}</td>
                    <td>{row.positive ?? 0}</td>
                    <td>{row.qualified ?? 0}</td>
                    <td>{row.converted ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </>
  );
}
