import { BadgeCheck, Handshake, Reply, Search, Send, ThumbsUp } from "lucide-react";

const STAGES = [
  { key: "sourced", icon: Search },
  { key: "contacted", icon: Send },
  { key: "replied", icon: Reply },
  { key: "positive", icon: ThumbsUp },
  { key: "qualified", icon: BadgeCheck },
  { key: "converted", icon: Handshake },
];

export default function FunnelPipeline({ counts = {} }) {
  const max = Math.max(...STAGES.map((s) => counts[s.key] || 0), 1);

  return (
    <div className="funnel">
      {STAGES.map((stage, index) => {
        const count = counts[stage.key] ?? 0;
        const prev = index > 0 ? counts[STAGES[index - 1].key] ?? 0 : null;
        const rate = prev ? `${Math.round((count / prev) * 100)}% of prev.` : index === 0 ? "Top of funnel" : "—";
        const Icon = stage.icon;
        return (
          <div key={stage.key} className="funnel-step">
            <div className="funnel-step-top">
              <span className="funnel-step-label">{stage.key}</span>
              <Icon size={14} strokeWidth={2} />
            </div>
            <span className="funnel-step-count">{count}</span>
            <div className="funnel-step-bar">
              <div className="funnel-step-fill" style={{ width: `${(count / max) * 100}%` }} />
            </div>
            <span className="funnel-step-rate">{rate}</span>
          </div>
        );
      })}
    </div>
  );
}
