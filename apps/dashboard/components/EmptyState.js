import { Inbox } from "lucide-react";

export default function EmptyState({ icon: Icon = Inbox, title, description, children }) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon size={20} strokeWidth={1.8} />
      </div>
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {children ? <div style={{ marginTop: 16 }}>{children}</div> : null}
    </div>
  );
}
