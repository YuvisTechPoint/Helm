import { CircleCheck, CircleX, Info, TriangleAlert } from "lucide-react";

const ICONS = {
  info: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  error: CircleX,
};

export default function Alert({ variant = "info", children }) {
  const Icon = ICONS[variant] ?? Info;
  return (
    <div className={`alert alert-${variant}`} role={variant === "error" ? "alert" : "status"}>
      <Icon size={16} strokeWidth={2} />
      <div className="alert-body">{children}</div>
    </div>
  );
}
