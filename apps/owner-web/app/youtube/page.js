import {
  CalendarClock,
  CircleCheck,
  Clock,
  Eye,
  FlaskConical,
  Gauge,
  Lock,
  Power,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Upload,
  Video,
} from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import EmptyState from "../../components/EmptyState";
import PageHeader from "../../components/PageHeader";
import RefreshLink from "../../components/RefreshLink";
import StatCard from "../../components/StatCard";
import { apiGet, formatNumber } from "../../lib/api";
import PivotPanel from "./PivotPanel";

export default async function YouTubePage() {
  const [data, videosRes, ypp, plan, pivotRes] = await Promise.all([
    apiGet("/youtube/status"),
    apiGet("/youtube/videos"),
    apiGet("/youtube/ypp?subscribers=0&watch_hours=0"),
    apiGet("/youtube/plan"),
    apiGet("/youtube/optimizer/pivot"),
  ]);
  const dry = data.last_dry_run;
  const exceptions = data.exceptions || [];
  const videos = videosRes.videos || [];
  const calendar = plan.calendar || [];

  return (
    <>
      <PageHeader
        title="YouTube engine"
        description="Private-first publishing until the channel audit is approved. The kill switch halts every upload. Metrics and one-change optimisation run after each publish."
      >
        <RefreshLink />
      </PageHeader>

      {data.error ? <Alert variant="error">{data.error}</Alert> : null}

      <PivotPanel pivot={pivotRes.pivot} />

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <StatCard icon={Gauge} tone="info" label="Quota left" value={formatNumber(data.quota_remaining)} hint="YouTube Data API units" />
        <StatCard icon={Upload} tone="accent" label="Uploads" value={formatNumber(videos.length || data.uploads || 0)} hint="Private until audit" />
        <StatCard icon={FlaskConical} tone="success" label="Dry run passed" value={dry ? dry.passed : "—"} hint={dry ? `${dry.uploads} uploads` : "Run from the engines page"} />
        <StatCard icon={TriangleAlert} tone={exceptions.length ? "danger" : "neutral"} label="Exceptions" value={exceptions.length} hint={exceptions.length ? "Needs review" : "All clear"} />
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-header">
            <h2 className="card-title"><ShieldCheck size={16} />Engine state</h2>
          </div>
          <div className="kv-list">
            <div className="kv-row">
              <span className="kv-key"><ShieldCheck size={15} />Audit approved</span>
              <Badge variant={data.audit_approved ? "success" : "warning"} dot>
                {data.audit_approved ? "Approved" : "Private only"}
              </Badge>
            </div>
            <div className="kv-row">
              <span className="kv-key"><Power size={15} />Kill switch</span>
              <Badge variant={data.kill_switch ? "danger" : "success"} dot>
                {data.kill_switch ? "Active" : "Off"}
              </Badge>
            </div>
            <div className="kv-row">
              <span className="kv-key"><Clock size={15} />Last dry run</span>
              <span className="kv-val">{dry ? `${dry.passed} topics · ${dry.uploads} uploads` : "Not run yet"}</span>
            </div>
            <div className="kv-row">
              <span className="kv-key"><Sparkles size={15} />Niche this week</span>
              <span className="kv-val">{plan.niche || "—"}</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h2 className="card-title"><Lock size={16} />Publishing policy</h2>
          </div>
          <div className="kv-list">
            <div className="kv-row"><span className="kv-key"><Eye size={15} />Default privacy</span><span className="kv-val">Private</span></div>
            <div className="kv-row"><span className="kv-key"><Sparkles size={15} />Synthetic media</span><span className="kv-val">Declared</span></div>
            <div className="kv-row"><span className="kv-key"><CalendarClock size={15} />Cadence cap</span><span className="kv-val">3 long + 5 Shorts / week</span></div>
            <div className="kv-row"><span className="kv-key"><Clock size={15} />YPP auto-apply</span><span className="kv-val">{ypp.auto_apply ? "On" : "Human only"}</span></div>
          </div>
        </div>
      </div>

      <div className="card card-flush" style={{ marginTop: 16 }}>
        <div className="card-header">
          <h2 className="card-title"><Video size={16} />Published catalog</h2>
        </div>
        {videos.length === 0 ? (
          <EmptyState icon={Upload} title="No uploads yet" description="Run the YouTube cycle or private dry-run from Run engines." />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>YouTube id</th>
                  <th>Privacy</th>
                </tr>
              </thead>
              <tbody>
                {videos.map((row) => (
                  <tr key={row.idempotency_key || row.youtube_id}>
                    <td className="cell-primary">{row.title || row.idempotency_key}</td>
                    <td className="cell-muted">{row.youtube_id}</td>
                    <td><Badge variant={row.privacy_status === "private" ? "warning" : "success"} dot>{row.privacy_status || "private"}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {calendar.length ? (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <h2 className="card-title"><CalendarClock size={16} />This week's calendar</h2>
          </div>
          <ul className="report-text">
            {calendar.slice(0, 8).map((item, index) => (
              <li key={index}>{item.slug || item.title || JSON.stringify(item)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="card card-flush" style={{ marginTop: 16 }}>
        <div className="card-header">
          <h2 className="card-title"><TriangleAlert size={16} />Open exceptions</h2>
          <Badge variant={exceptions.length ? "danger" : "success"} dot>
            {exceptions.length ? `${exceptions.length} open` : "Clear"}
          </Badge>
        </div>
        {exceptions.length === 0 ? (
          <EmptyState icon={CircleCheck} title="No exceptions" description="Quality gate, publish, and policy checks are clean." />
        ) : (
          exceptions.map((row) => (
            <div key={row.id} className="list-item">
              <div className="list-item-main">
                <span className="stat-icon tone-danger"><TriangleAlert size={15} /></span>
                <div>
                  <h4>{row.kind}</h4>
                  <p>{row.message}</p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </>
  );
}
