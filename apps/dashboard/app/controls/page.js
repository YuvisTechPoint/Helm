import { CalendarCheck, CreditCard, FileSignature, Mail, MessageCircle, MessageSquareText, Phone, PlugZap, ShieldCheck } from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import PageHeader from "../../components/PageHeader";
import RefreshLink from "../../components/RefreshLink";
import { apiGet } from "../../lib/api";
import DataRightsPanel from "./DataRightsPanel";
import KillSwitchPanel from "./KillSwitchPanel";

const PROVIDERS = [
  { key: "email", label: "Email sending", icon: Mail },
  { key: "whatsapp", label: "WhatsApp Cloud API", icon: MessageCircle },
  { key: "sms", label: "Twilio SMS", icon: MessageSquareText },
  { key: "voice", label: "Vapi voice", icon: Phone },
  { key: "calendar", label: "Cal.com booking", icon: CalendarCheck },
  { key: "esign", label: "E-signature", icon: FileSignature },
  { key: "payments", label: "Payments", icon: CreditCard },
];

const GUARANTEES = [
  "No LinkedIn automation or scraping",
  "No cold WhatsApp, SMS, or AI calls — consent first",
  "The agent says it is an AI whenever asked",
  "Price never goes below the configured floor",
  "Every send passes the policy guard and is audit-logged",
  "Automation freezes once a client is handed off",
];

export default async function ControlsPage() {
  const [controls, channels] = await Promise.all([apiGet("/acquisition/controls"), apiGet("/acquisition/channels")]);
  const error = controls.error || channels.error;
  const status = channels.channels || {};

  return (
    <>
      <PageHeader
        title="Controls & compliance"
        description="Stop any part of the engine instantly, check which providers are live, and handle consent and data-rights requests."
      >
        <RefreshLink />
      </PageHeader>

      {error ? <Alert variant="error">{error}</Alert> : null}

      <div className="grid grid-dash">
        <div className="stack-16">
          {controls.error ? null : <KillSwitchPanel controls={controls} />}
          <DataRightsPanel />
        </div>

        <div className="stack-16">
          <div className="card">
            <div className="card-header">
              <h2 className="card-title"><PlugZap size={16} />Providers</h2>
            </div>
            <div className="kv-list">
              {PROVIDERS.map(({ key, label, icon: Icon }) => {
                const row = status[key] || {};
                return (
                  <div key={key} className="kv-row">
                    <span className="kv-key"><Icon size={14} />{label}</span>
                    <span className="kv-val">
                      {row.killed ? (
                        <Badge variant="danger" dot>Stopped</Badge>
                      ) : row.live ? (
                        <Badge variant="success" dot>Live · {row.provider}</Badge>
                      ) : (
                        <Badge variant="neutral" dot>Sandbox</Badge>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
            <p className="form-hint" style={{ marginTop: 12 }}>
              Sandbox providers record messages locally. Add the credentials in <code>.env</code> to go live.
            </p>
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
