import { Calculator, Handshake, IndianRupee, PieChart, Receipt, ReceiptText, TrendingUp, Wallet } from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import EmptyState from "../../components/EmptyState";
import PageHeader from "../../components/PageHeader";
import RefreshLink from "../../components/RefreshLink";
import StatCard from "../../components/StatCard";
import { apiGet, formatCents, formatNumber } from "../../lib/api";

const DEAL_STATUS = {
  booked: { label: "Meeting booked", variant: "info" },
  proposal_sent: { label: "Proposal sent", variant: "info" },
  signed: { label: "Signed", variant: "success" },
  payment_pending: { label: "Awaiting payment", variant: "warning" },
  paid: { label: "Paid", variant: "success" },
  declined: { label: "Declined", variant: "neutral" },
  cancelled: { label: "Cancelled", variant: "neutral" },
  stalled: { label: "Stalled", variant: "danger" },
};

const BAR_TONES = ["", "tone-bar-info", "tone-bar-success", "tone-bar-warning"];

export default async function MoneyPage() {
  const [data, dealData] = await Promise.all([apiGet("/acquisition/money"), apiGet("/acquisition/deals")]);
  const categories = Object.entries(data.spend_by_category || {}).sort((a, b) => b[1] - a[1]);
  const maxCategory = categories.reduce((max, [, value]) => Math.max(max, value), 0);
  const deals = [...(dealData.deals || [])].reverse();
  const roi = data.spend_cents ? (data.revenue_cents || 0) / data.spend_cents : null;

  return (
    <>
      <PageHeader
        title="Revenue & spend"
        description="Cost per converted client (CPCC) is the north-star metric. Every paisa of data, sending, and model spend is tracked against the deals it produced."
      >
        <RefreshLink />
      </PageHeader>

      {data.error ? <Alert variant="error">{data.error}</Alert> : null}

      <div className="grid grid-4">
        <StatCard icon={Wallet} tone="accent" label="Total spend" value={formatCents(data.spend_cents)} hint={`${formatNumber(categories.length)} categories`} />
        <StatCard icon={Receipt} tone="info" label="CPCC" value={data.cpcc_cents != null ? formatCents(data.cpcc_cents) : "—"} hint={`${formatNumber(data.converted ?? 0)} converted clients`} />
        <StatCard icon={IndianRupee} tone="success" label="Revenue collected" value={formatCents(data.revenue_cents ?? 0)} hint={roi != null ? `${roi.toFixed(1)}× return on spend` : "No spend yet"} />
        <StatCard icon={TrendingUp} tone="warning" label="Open pipeline" value={formatCents(data.pipeline_value_cents)} hint={`${formatNumber(data.deals ?? 0)} deals total`} />
      </div>

      <div className="grid grid-dash" style={{ marginTop: 16 }}>
        <div className="card card-flush">
          <div className="card-header">
            <h2 className="card-title"><Handshake size={16} />Deals</h2>
          </div>
          {deals.length === 0 ? (
            <EmptyState icon={ReceiptText} title="No deals yet" description="Deals appear when a qualified lead books a meeting or receives a proposal." />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Client</th>
                    <th>Value</th>
                    <th>Deposit</th>
                    <th>Paid</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {deals.map((deal, index) => {
                    const status = DEAL_STATUS[deal.status] || { label: deal.status, variant: "neutral" };
                    return (
                      <tr key={`${deal.lead_email}-${index}`}>
                        <td><span className="cell-primary">{deal.lead_email}</span></td>
                        <td>{formatCents(deal.price_cents)}</td>
                        <td className="cell-muted">{deal.deposit_cents ? formatCents(deal.deposit_cents) : "—"}</td>
                        <td className="cell-muted">
                          {deal.paid_cents ? formatCents(deal.paid_cents) : deal.partial_paid_cents ? `${formatCents(deal.partial_paid_cents)} (partial)` : "—"}
                        </td>
                        <td>
                          <Badge variant={status.variant} dot>{status.label}</Badge>
                          {deal.handoff ? <span style={{ marginLeft: 6 }}><Badge variant="accent">Handed off</Badge></span> : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="stack-16">
          <div className="card">
            <div className="card-header">
              <h2 className="card-title"><PieChart size={16} />Spend by category</h2>
            </div>
            {categories.length === 0 ? (
              <p className="prose-muted">No spend recorded yet.</p>
            ) : (
              <div className="bar-list">
                {categories.map(([name, value], index) => (
                  <div key={name}>
                    <div className="bar-row-head">
                      <span>{name.replace(/_/g, " ")}</span>
                      <span>{formatCents(value)}</span>
                    </div>
                    <div className="bar-track">
                      <div className={`bar-fill ${BAR_TONES[index % BAR_TONES.length]}`} style={{ width: `${maxCategory ? (value / maxCategory) * 100 : 0}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <h2 className="card-title"><Calculator size={16} />How this is calculated</h2>
            </div>
            <p className="prose-muted">
              CPCC = total spend ÷ converted clients. Revenue counts only deals that were paid or signed and handed off.
              Open pipeline is the value of booked, proposed, signed, and awaiting-payment deals. Each business has a
              hard budget; outreach stops automatically when it runs out.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
