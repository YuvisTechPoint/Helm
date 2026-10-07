import { BrainCircuit, CalendarRange, FileText, Gauge, GitCommitHorizontal, Scale, SlidersHorizontal, Target } from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import EmptyState from "../../components/EmptyState";
import PageHeader from "../../components/PageHeader";
import RefreshLink from "../../components/RefreshLink";
import StatCard from "../../components/StatCard";
import { apiGet } from "../../lib/api";
import LearningActions from "./LearningActions";

function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

function WeightBar({ label, value }) {
  const pct = Math.min(100, ((value ?? 1) / 2) * 100);
  return (
    <div>
      <div className="bar-row-head">
        <span>{label}</span>
        <span>×{(value ?? 1).toFixed(2)}</span>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default async function LearningPage() {
  const [learning, reports, evaluation, experiments] = await Promise.all([
    apiGet("/acquisition/learning"),
    apiGet("/acquisition/reports"),
    apiGet("/acquisition/eval"),
    apiGet("/acquisition/experiments"),
  ]);
  const error = learning.error || reports.error || evaluation.error;
  const weights = learning.weights || {};
  const volume = learning.volume || {};
  const prompt = learning.prompt || {};
  const changes = [...(experiments.changes || []), ...(learning.last_run?.changes || []).filter((c) => c.dimension === "score_weights")]
    .sort((a, b) => String(b.at).localeCompare(String(a.at)))
    .slice(0, 12);
  const reportRows = (reports.reports || []).filter(Boolean);
  const accuracy = evaluation.accuracy != null ? `${(evaluation.accuracy * 100).toFixed(1)}%` : "—";

  return (
    <>
      <PageHeader
        title="Learning & reports"
        description="What the engine learned, what it changed and why, and the monthly report sent to you."
      >
        <RefreshLink />
      </PageHeader>

      {error ? <Alert variant="error">{error}</Alert> : null}

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <StatCard icon={Gauge} tone={evaluation.accuracy >= 0.95 ? "success" : "warning"} label="Reply classifier" value={accuracy} hint={`${evaluation.cases ?? 0} labelled cases · gate 95%`} />
        <StatCard icon={Target} tone="accent" label="Weekly target" value={volume.target_qualified_per_week ?? "—"} hint="Qualified leads per week" />
        <StatCard
          icon={CalendarRange}
          tone={volume.capacity_limited ? "warning" : "info"}
          label="Daily contacts"
          value={volume.daily_contacts_planned ?? "—"}
          hint={volume.capacity_limited ? `Capped by mailboxes (${volume.daily_cap}/day)` : `${((volume.observed_rate ?? 0) * 100).toFixed(1)}% contact → qualified`}
        />
        <StatCard
          icon={Scale}
          tone={weights.status === "trained" ? "success" : "neutral"}
          label="Lead scoring"
          value={weights.status === "trained" ? "Trained" : "Default"}
          hint={weights.samples ? `${weights.samples} samples · ${weights.positives} positive` : "Needs 20 contacted leads"}
        />
      </div>

      <div className="grid grid-dash">
        <div className="stack-16">
          <div className="card">
            <div className="card-header">
              <h2 className="card-title"><GitCommitHorizontal size={16} />What changed and why</h2>
            </div>
            {changes.length === 0 ? (
              <EmptyState icon={GitCommitHorizontal} title="No changes yet" description="Variants are promoted only after enough sends to be statistically meaningful." />
            ) : (
              <div className="timeline">
                {changes.map((change, index) => (
                  <div key={`${change.at}-${index}`} className="timeline-item">
                    <span className="stat-icon tone-accent"><BrainCircuit size={14} /></span>
                    <div>
                      <h4>{change.summary}</h4>
                      <p>{change.why}</p>
                      {change.retired?.length ? <p>Retired: {change.retired.join(", ")}</p> : null}
                      {change.challenger ? <p>New challenger: {change.challenger}</p> : null}
                      <div className="timeline-time">{formatDate(change.at)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <h2 className="card-title"><FileText size={16} />Monthly reports</h2>
            </div>
            {reportRows.length === 0 ? (
              <EmptyState icon={FileText} title="No reports yet" description="A plain-language report is generated on the 1st of every month." />
            ) : (
              <div className="stack-16">
                {reportRows.map((report) => (
                  <div key={report.month}>
                    <div className="bar-row-head" style={{ marginBottom: 8 }}>
                      <span style={{ textTransform: "none", fontWeight: 600, color: "var(--text)" }}>{report.month}</span>
                      <span className="cell-muted" style={{ fontWeight: 400 }}>{formatDate(report.generated_at)}</span>
                    </div>
                    <ul className="report-text">
                      {(report.lines || []).map((line, index) => (
                        <li key={index}>{line}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="stack-16">
          <div className="card">
            <div className="card-header">
              <h2 className="card-title"><SlidersHorizontal size={16} />Run & tune</h2>
            </div>
            <LearningActions target={volume.target_qualified_per_week} />
          </div>

          <div className="card">
            <div className="card-header">
              <h2 className="card-title"><Scale size={16} />Score weights</h2>
              <span className="card-subtitle">Updated {formatDate(weights.trained_at)}</span>
            </div>
            <div className="bar-list">
              <WeightBar label="Fit" value={weights.fit} />
              <WeightBar label="Intent" value={weights.intent} />
              <WeightBar label="Reach" value={weights.reach} />
            </div>
            <p className="form-hint" style={{ marginTop: 12 }}>
              Score = fit<sup>a</sup> × intent<sup>b</sup> × reach. Exponents are refit weekly on reply outcomes and clamped to 0.5–2.
            </p>
          </div>

          <div className="card">
            <div className="card-header">
              <h2 className="card-title"><Gauge size={16} />Classifier eval</h2>
              <Badge variant={prompt.active ? "success" : "neutral"} dot>{prompt.active ? `${prompt.name} live` : "Not activated"}</Badge>
            </div>
            <div className="kv-list">
              {Object.entries(evaluation.per_label || {}).map(([label, bucket]) => (
                <div key={label} className="kv-row">
                  <span className="kv-key" style={{ textTransform: "capitalize" }}>{label.replace(/_/g, " ")}</span>
                  <span className="kv-val">{bucket.correct}/{bucket.total}</span>
                </div>
              ))}
            </div>
            {(evaluation.failures || []).length ? (
              <Alert variant="warning">{evaluation.failures.length} case(s) misclassified — new prompts cannot go live until fixed.</Alert>
            ) : null}
          </div>
        </div>
      </div>
    </>
  );
}
