import {
  BrainCircuit,
  Building2,
  FlaskConical,
  LayoutDashboard,
  Mail,
  MessagesSquare,
  MonitorPlay,
  Play,
  Radar,
  ShieldAlert,
  ShieldCheck,
  Wallet,
} from "lucide-react";

export const NAV_SECTIONS = [
  {
    label: "Overview",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/autopilot", label: "Autopilot", icon: Radar },
      { href: "/actions", label: "Run engines", icon: Play },
      { href: "/escalations", label: "Escalations", icon: ShieldAlert },
      { href: "/controls", label: "Controls & compliance", icon: ShieldCheck },
    ],
  },
  {
    label: "Acquisition",
    items: [
      { href: "/profile", label: "Service profile", icon: Building2 },
      { href: "/threads", label: "Conversations", icon: MessagesSquare },
      { href: "/health", label: "Mailboxes", icon: Mail },
      { href: "/money", label: "Revenue", icon: Wallet },
      { href: "/experiments", label: "Experiments", icon: FlaskConical },
      { href: "/learning", label: "Learning & reports", icon: BrainCircuit },
    ],
  },
  {
    label: "YouTube",
    items: [{ href: "/youtube", label: "Channel engine", icon: MonitorPlay }],
  },
];

export function findNavItem(pathname) {
  for (const section of NAV_SECTIONS) {
    for (const item of section.items) {
      const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
      if (active) return { section: section.label, item };
    }
  }
  return null;
}
