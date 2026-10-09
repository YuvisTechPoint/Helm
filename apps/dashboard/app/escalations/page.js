import { MonitorPlay, ShieldAlert, ShieldCheck } from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import EmptyState from "../../components/EmptyState";
import PageHeader from "../../components/PageHeader";
import RefreshLink from "../../components/RefreshLink";
import { apiGet } from "../../lib/api";
import ResolveButton from "./ResolveButton";

export default async function EscalationsPage() {
  const yt = await apiGet("/youtube/exceptions");
  const rows = yt.exceptions || [];
  const error = yt.error;

  return (
    <>
      <PageHeader
        title="Escalations"
        description="Policy alerts, publish blocks, and kill-switch events that need your review."
      >
        <Badge variant={rows.length ? "danger" : "success"} dot>
          {rows.length ? `${rows.length} open` : "Clear"}
        </Badge>
        <RefreshLink />
      </PageHeader>

      {error && rows.length === 0 ? <Alert variant="error">{error}</Alert> : null}

      <div className="card card-flush">
        <div className="card-header">
          <h2 className="card-title"><ShieldAlert size={16} />Owner queue</h2>
          <span className="cell-muted" style={{ fontSize: 12.5 }}>Review promptly</span>
        </div>
        {rows.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title="Queue is empty"
            description="Escalations appear on policy strikes, publish blocks, kill-switch events, or niche pivot recommendations."
          />
        ) : (
          rows.map((row, index) => (
            <div key={`${row.id}-${index}`} className="list-item">
              <div className="list-item-main">
                <span className="stat-icon tone-info">
                  <MonitorPlay size={15} />
                </span>
                <div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 3 }}>
                    <h4 style={{ margin: 0 }}>{String(row.kind).replace(/_/g, " ")}</h4>
                    <Badge variant="info">youtube</Badge>
                  </div>
                  <p>{row.message}</p>
                </div>
              </div>
              <ResolveButton id={row.id} />
            </div>
          ))
        )}
      </div>
    </>
  );
}
