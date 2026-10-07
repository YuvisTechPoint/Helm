import Link from "next/link";
import { CalendarClock, FlaskConical, GitBranch, History, ListOrdered, MessageSquareQuote, Send, ThumbsUp, Type } from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import EmptyState from "../../components/EmptyState";
import PageHeader from "../../components/PageHeader";
import RefreshLink from "../../components/RefreshLink";
import StatCard from "../../components/StatCard";
import { apiGet } from "../../lib/api";

const DIMENSIONS = {
  angle: { label: "Opening angle", icon: MessageSquareQuote },
  subject: { label: "Subject line", icon: Type },
  sequence_length: { label: "Sequence length", icon: ListOrdered },
  send_time: { label: "Send time", icon: CalendarClock },
};

function rate(row) {
  return row.sends > 0 ? row.positive / row.sends : null;
}

export default async function ExperimentsPage() {
  const data = await apiGet("/acquisition/experiments");
  const groups = data.by_dimension || {};
  const rows = data.experiments || [];
  const live = rows.filter((row) => !row.retired);
  const sends = Object.values(groups)[0]?.reduce((sum, row) => sum + (row.sends || 0), 0) ?? 0;
  const positive = Object.values(groups)[0]?.reduce((sum, row) => sum + (row.positive || 0), 0) ?? 0;
  const changes = [...(data.changes || [])].reverse();

  return (
    <>
      <PageHeader
        title="Experiments"
        description="Each lead is assigned one variant per dimension. Weekly, a winner is promoted only after enough sends, losers retire, and a new challenger enters."
      >
        <RefreshLink />
      </PageHeader>

      {data.error ? <Alert variant="error">{data.error}</Alert> : null}

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <StatCard icon={Send} tone="info" label="Leads in tests" value={sends} hint="Assignments per dimension" />
        <StatCard icon={ThumbsUp} tone="success" label="Positive replies" value={positive} hint={sends ? `${((positive / sends) * 100).toFixed(1)}% positive rate` : "No sends yet"} />
        <StatCard icon={GitBranch} tone="accent" label="Live variants" value={live.length} hint={`${rows.length - live.length} retired`} />
        <StatCard icon={History} tone="warning" label="Promotions" value={changes.length} hint="See the learning page for details" />
      </div>

      {Object.keys(groups).length === 0 && !data.error ? (
        <div className="card">
          <EmptyState icon={FlaskConical} title="No experiments" description="Variants appear once outreach sequences start sending." />
        </div>
      ) : (
        <div className="grid grid-2">
          {Object.entries(groups).map(([dimension, variants]) => {
            const meta = DIMENSIONS[dimension] || { label: dimension, icon: FlaskConical };
            const Icon = meta.icon;
            const best = Math.max(0, ...variants.filter((row) => !row.retired).map((row) => rate(row) ?? 0));
            return (
              <div key={dimension} className="card card-flush">
                <div className="card-header">
                  <h2 className="card-title"><Icon size={16} />{meta.label}</h2>
                </div>
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Variant</th>
                        <th>Sends</th>
                        <th>Positive</th>
                        <th>Rate</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {variants.map((row) => {
                        const value = rate(row);
                        const leading = !row.retired && value != null && value === best && best > 0;
                        return (
                          <tr key={row.name}>
                            <td><span className="cell-primary">{row.name.replace(/[-_]/g, " ")}</span></td>
                            <td>{row.sends}</td>
                            <td>{row.positive}</td>
                            <td>
                              {value != null ? `${(value * 100).toFixed(1)}%` : "—"}
                              {leading ? <span style={{ marginLeft: 6 }}><Badge variant="accent">Leading</Badge></span> : null}
                            </td>
                            <td>
                              <Badge variant={row.active ? "success" : row.retired ? "neutral" : "info"} dot>
                                {row.active ? "Champion" : row.retired ? "Retired" : "Challenger"}
                              </Badge>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {changes.length ? (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <h2 className="card-title"><History size={16} />Recent promotions</h2>
            <Link href="/learning" className="btn btn-ghost btn-sm">View all</Link>
          </div>
          <div className="timeline">
            {changes.slice(0, 5).map((change, index) => (
              <div key={`${change.at}-${index}`} className="timeline-item">
                <span className="stat-icon tone-accent"><GitBranch size={14} /></span>
                <div>
                  <h4>{change.summary}</h4>
                  <p>{change.why}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </>
  );
}
