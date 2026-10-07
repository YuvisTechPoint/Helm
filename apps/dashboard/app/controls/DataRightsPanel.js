"use client";

import { useState } from "react";
import { Download, FileCheck2, LoaderCircle, Search, ShieldOff, Trash2, UserX } from "lucide-react";
import Badge from "../../components/Badge";
import EmptyState from "../../components/EmptyState";
import { apiDelete, apiGet, apiPost } from "../../lib/api";

function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

export default function DataRightsPanel() {
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState(null);
  const [consents, setConsents] = useState([]);
  const [busy, setBusy] = useState(null);
  const [message, setMessage] = useState(null);
  const [confirmErase, setConfirmErase] = useState(false);

  const target = email.trim().toLowerCase();

  async function lookup(event) {
    event?.preventDefault();
    if (!target) return;
    setBusy("lookup");
    setMessage(null);
    setConfirmErase(false);
    const data = await apiGet(`/acquisition/consent/${encodeURIComponent(target)}`);
    setBusy(null);
    if (data.error) {
      setMessage({ tone: "error", text: data.error });
      return;
    }
    setSubject(target);
    setConsents(data.consents || []);
  }

  async function exportData() {
    setBusy("export");
    const data = await apiGet(`/acquisition/leads/${encodeURIComponent(subject)}/export`);
    setBusy(null);
    if (data.error) {
      setMessage({ tone: "error", text: data.error });
      return;
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `data-export-${subject}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setMessage({ tone: "success", text: "Export downloaded." });
  }

  async function withdrawAll() {
    setBusy("withdraw");
    const data = await apiPost("/acquisition/consent/withdraw", { email: subject });
    setBusy(null);
    if (data.error) {
      setMessage({ tone: "error", text: data.error });
      return;
    }
    setMessage({ tone: "success", text: `Withdrew ${data.withdrawn ?? 0} consent record(s).` });
    await lookup();
  }

  async function erase() {
    setBusy("erase");
    const data = await apiDelete(`/acquisition/leads/${encodeURIComponent(subject)}`);
    setBusy(null);
    setConfirmErase(false);
    if (data.error) {
      setMessage({ tone: "error", text: data.error });
      return;
    }
    const removed = data.removed || {};
    setMessage({
      tone: "success",
      text: `Erased ${removed.leads ?? 0} lead, ${removed.conversations ?? 0} thread, ${removed.consents ?? 0} consent record(s). Address kept on the do-not-contact list.`,
    });
    setConsents([]);
  }

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title"><FileCheck2 size={16} />Consent & data rights</h2>
      </div>
      <p className="prose-muted" style={{ marginBottom: 14 }}>
        Look up a contact to see the lawful basis for each channel, export everything held about them, or erase it.
        Erasure keeps only a suppression entry so they are never contacted again.
      </p>

      <form className="search-bar" onSubmit={lookup}>
        <div className="input-icon">
          <Search size={14} />
          <input
            className="input"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="prospect@company.com"
            aria-label="Contact email"
          />
        </div>
        <button type="submit" className="btn btn-secondary" disabled={!target || busy !== null}>
          {busy === "lookup" ? <LoaderCircle size={14} className="spin" /> : <Search size={14} />}
          Look up
        </button>
      </form>

      {subject ? (
        <>
          {consents.length === 0 ? (
            <EmptyState icon={ShieldOff} title="No consent records" description={`Nothing recorded for ${subject}. Cold email relies on legitimate interest; other channels need consent.`} />
          ) : (
            <div className="table-wrap" style={{ marginBottom: 14 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Channel</th>
                    <th>Basis</th>
                    <th>Source</th>
                    <th>Recorded</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {consents.map((row, index) => (
                    <tr key={`${row.channel}-${index}`}>
                      <td className="cell-primary" style={{ textTransform: "capitalize" }}>{row.channel}</td>
                      <td className="cell-muted">{(row.basis || "").replace(/_/g, " ")}</td>
                      <td className="cell-muted" title={row.evidence || ""}>{row.source || "—"}</td>
                      <td className="cell-muted">{formatDate(row.recorded_at)}</td>
                      <td>
                        <Badge variant={row.withdrawn_at ? "neutral" : "success"} dot>
                          {row.withdrawn_at ? "Withdrawn" : "Active"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="inline-actions" style={{ marginTop: 14 }}>
            <button type="button" className="btn btn-secondary btn-sm" onClick={exportData} disabled={busy !== null}>
              {busy === "export" ? <LoaderCircle size={14} className="spin" /> : <Download size={14} />}
              Export data
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={withdrawAll} disabled={busy !== null || consents.every((row) => row.withdrawn_at)}>
              {busy === "withdraw" ? <LoaderCircle size={14} className="spin" /> : <UserX size={14} />}
              Withdraw all consent
            </button>
            {confirmErase ? (
              <>
                <button type="button" className="btn btn-danger btn-sm" onClick={erase} disabled={busy !== null}>
                  {busy === "erase" ? <LoaderCircle size={14} className="spin" /> : <Trash2 size={14} />}
                  Confirm permanent erase
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConfirmErase(false)}>Cancel</button>
              </>
            ) : (
              <button type="button" className="btn btn-danger btn-sm" onClick={() => setConfirmErase(true)} disabled={busy !== null}>
                <Trash2 size={14} />
                Erase contact
              </button>
            )}
          </div>
        </>
      ) : null}

      {message ? <div className={`toast toast-${message.tone}`}>{message.text}</div> : null}
    </div>
  );
}
