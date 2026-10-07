import { MonitorPlay, ShieldAlert, ShieldCheck, Target } from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import EmptyState from "../../components/EmptyState";
import PageHeader from "../../components/PageHeader";
import RefreshLink from "../../components/RefreshLink";
import { apiGet } from "../../lib/api";
import ResolveButton from "./ResolveButton";

export default async function EscalationsPage() {
  const [acq, yt] = await Promise.all([apiGet("/acquisition/escalations"), apiGet("/youtube/exceptions")]);

  const rows = [
    ...(acq.escalations || []).map((row) => ({ ...row, scope: "acquisition" })),
    ...(yt.exceptions || []).map((row) => ({ ...row, scope: "youtube" })),
  ];

  const error = acq.error || yt.error;

  return (
    <>
      <PageHeader
        title="Escalations"
        description="The only queue that needs you. Prospects receive a holding reply until you resolve; resolutions feed back into the profile."
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
          <span className="cell-muted" style={{ fontSize: 12.5 }}>24-hour SLA</span>
        </div>
        {rows.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title="Queue is empty"
            description="Escalations appear on legal threats, out-of-scope pricing, low-confidence replies, double critic failures, or YouTube policy alerts."
          />
        ) : (
          rows.map((row, index) => {
            const ScopeIcon = row.scope === "youtube" ? MonitorPlay : Target;
            return (
              <div key={`${row.id}-${index}`} className="list-item">
                <div className="list-item-main">
                  <span className={`stat-icon ${row.scope === "youtube" ? "tone-info" : "tone-warning"}`}>
                    <ScopeIcon size={15} />
                  </span>
                  <div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 3 }}>
                      <h4 style={{ margin: 0 }}>{String(row.kind).replace(/_/g, " ")}</h4>
                      <Badge variant={row.scope === "youtube" ? "info" : "warning"}>{row.scope}</Badge>
                    </div>
                    <p>{row.message}</p>
                  </div>
                </div>
                <ResolveButton id={row.id} scope={row.scope} />
              </div>
            );
          })
        )}
      </div>
    </>
  );
}
