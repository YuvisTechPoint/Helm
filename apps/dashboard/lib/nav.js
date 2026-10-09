import {
  LayoutDashboard,
  MonitorPlay,
  Play,
  Radar,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

export const NAV_SECTIONS = [
  {
    label: "Overview",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/autopilot", label: "Autopilot", icon: Radar },
      { href: "/actions", label: "Run pipeline", icon: Play },
      { href: "/escalations", label: "Escalations", icon: ShieldAlert },
      { href: "/controls", label: "Controls & compliance", icon: ShieldCheck },
    ],
  },
  {
    label: "Channel",
    items: [{ href: "/youtube", label: "YouTube engine", icon: MonitorPlay }],
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
