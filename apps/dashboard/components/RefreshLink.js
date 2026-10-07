"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { RefreshCw } from "lucide-react";

export default function RefreshLink() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  return (
    <button
      type="button"
      className="btn btn-secondary btn-sm"
      onClick={() => startTransition(() => router.refresh())}
      disabled={pending}
    >
      <RefreshCw size={14} strokeWidth={2} className={pending ? "spin" : undefined} />
      Refresh
    </button>
  );
}
