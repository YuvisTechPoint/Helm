"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Play } from "lucide-react";
import ApiStatus from "./ApiStatus";
import { findNavItem } from "../lib/nav";

export default function Topbar() {
  const pathname = usePathname();
  const match = findNavItem(pathname);

  return (
    <header className="topbar">
      <div className="breadcrumb">
        <span>{match?.section ?? "Overview"}</span>
        <ChevronRight size={14} />
        <span className="breadcrumb-current">{match?.item.label ?? "Page"}</span>
      </div>
      <div className="topbar-actions">
        <ApiStatus />
        {pathname !== "/actions" ? (
          <Link href="/actions" className="btn btn-primary btn-sm">
            <Play size={14} strokeWidth={2.2} />
            Run engines
          </Link>
        ) : null}
      </div>
    </header>
  );
}
