import Link from "next/link";
import { Bot, Mail, MessageCircle, MessageSquareText, MessagesSquare, Phone, Play, Search, User, X } from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import EmptyState from "../../components/EmptyState";
import PageHeader from "../../components/PageHeader";
import RefreshLink from "../../components/RefreshLink";
import { apiGet } from "../../lib/api";

const CHANNEL_ICONS = { email: Mail, whatsapp: MessageCircle, sms: MessageSquareText, voice: Phone };

const STATE_VARIANT = { open: "info", escalated: "danger", handed_off: "success", closed: "neutral" };

function formatTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

export default async function ThreadsPage({ searchParams }) {
  const params = (await searchParams) || {};
  const query = typeof params.q === "string" ? params.q.trim() : "";
  const data = await apiGet(`/acquisition/conversations${query ? `?q=${encodeURIComponent(query)}` : ""}`);
  const rows = data.conversations || [];

  return (
    <>
      <PageHeader
        title="Conversations"
        description="Every prospect thread across email, WhatsApp, SMS, and calls. Replies are drafted from your service profile and checked by the critic before sending."
      >
        <RefreshLink />
      </PageHeader>

      {data.error ? <Alert variant="error">{data.error}</Alert> : null}

      <form className="search-bar" action="/threads">
        <div className="input-icon">
          <Search size={14} />
          <input className="input" name="q" defaultValue={query} placeholder="Search by email or message text" aria-label="Search conversations" />
        </div>
        <button type="submit" className="btn btn-secondary">Search</button>
        {query ? (
          <Link href="/threads" className="btn btn-ghost">
            <X size={14} />
            Clear
          </Link>
        ) : null}
      </form>

      {rows.length === 0 && !data.error ? (
        <div className="card">
          {query ? (
            <EmptyState icon={Search} title="No matches" description={`No thread mentions “${query}”.`} />
          ) : (
            <EmptyState
              icon={MessagesSquare}
              title="No conversations yet"
              description="Run the acquisition demo to seed a full thread from first touch to handoff."
            >
              <Link href="/actions" className="btn btn-primary btn-sm">
                <Play size={14} strokeWidth={2.2} />
                Run engines
              </Link>
            </EmptyState>
          )}
        </div>
      ) : (
        <div className="thread-list">
          {rows.map((row, index) => (
            <div key={`${row.lead_email}-${index}`} className="thread-card">
              <div className="thread-header">
                <div className="thread-who">
                  <span className="avatar">{row.lead_email?.slice(0, 2)}</span>
                  <div style={{ minWidth: 0 }}>
                    <div className="thread-email">{row.lead_email}</div>
                    <div className="thread-count">{(row.messages || []).length} messages</div>
                  </div>
                </div>
                <Badge variant={STATE_VARIANT[row.state] || "neutral"} dot>{(row.state || "open").replace(/_/g, " ")}</Badge>
              </div>
              <div className="thread-messages">
                {(row.messages || []).map((message, msgIndex) => {
                  const inbound = message.direction === "inbound";
                  const ChannelIcon = CHANNEL_ICONS[message.channel] || Mail;
                  return (
                    <div key={msgIndex} className={`message message-${inbound ? "inbound" : "outbound"}`}>
                      <div className="message-meta">
                        {inbound ? <User size={12} /> : <Bot size={12} />}
                        {inbound ? "Prospect" : "Agent"}
                        <ChannelIcon size={12} aria-label={message.channel || "email"} />
                        {message.label ? ` · ${message.label.replace(/_/g, " ")}` : ""}
                        {message.handover ? " · handover" : ""}
                        {message.blocked ? " · blocked by policy" : ""}
                        {message.at ? ` · ${formatTime(message.at)}` : ""}
                      </div>
                      {message.body}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
