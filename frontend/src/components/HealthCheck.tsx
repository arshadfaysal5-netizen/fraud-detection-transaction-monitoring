"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

type Health = {
  status: string;
  service: string;
};

export default function HealthCheck() {
  const [state, setState] = useState<"checking" | "ok" | "down">("checking");

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`, { cache: "no-store" })
      .then((r) => r.json())
      .then((h: Health) => setState(h.status === "ok" ? "ok" : "down"))
      .catch(() => setState("down"));
  }, []);

  const dot =
    state === "checking"
      ? "bg-amber-400"
      : state === "ok"
        ? "bg-emerald-500"
        : "bg-red-500";

  const label =
    state === "checking"
      ? "Checking backend…"
      : state === "ok"
        ? "Backend API online"
        : "Backend API unreachable";

  return (
    <div className="flex items-center gap-2 rounded-full border border-zinc-200 px-4 py-1.5 text-sm text-zinc-600">
      <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
      {label}
    </div>
  );
}