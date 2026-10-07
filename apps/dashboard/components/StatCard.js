export default function StatCard({ icon: Icon, label, value, hint, tone = "accent" }) {
  return (
    <div className="card stat-card">
      <div className="stat-head">
        <span className="stat-label">{label}</span>
        {Icon ? (
          <span className={`stat-icon tone-${tone}`}>
            <Icon size={15} strokeWidth={2} />
          </span>
        ) : null}
      </div>
      <span className="stat-value">{value}</span>
      {hint ? <span className="stat-hint">{hint}</span> : null}
    </div>
  );
}
