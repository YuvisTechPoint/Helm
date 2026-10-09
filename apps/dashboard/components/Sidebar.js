"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Server } from "lucide-react";
import BrandMark from "./BrandMark";
import { NAV_SECTIONS } from "../lib/nav";

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <Link href="/" className="sidebar-brand">
        <BrandMark />
        <div className="brand-text">
          <span className="brand-name">YouTube Engine</span>
          <span className="brand-sub">Channel control plane</span>
        </div>
      </Link>
      <nav className="sidebar-nav" aria-label="Primary">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="nav-section">
            <div className="nav-section-label">{section.label}</div>
            {section.items.map((item) => {
              const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-link${active ? " active" : ""}`}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon size={16} strokeWidth={1.9} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span className="env-chip">
          <Server size={12} strokeWidth={2} />
          Single tenant
        </span>
        <span>v0.1 · MIT</span>
      </div>
    </aside>
  );
}
