export default function Badge({ variant = "neutral", dot = false, children }) {
  return (
    <span className={`badge badge-${variant}`}>
      {dot ? <span className="badge-dot" /> : null}
      {children}
    </span>
  );
}
