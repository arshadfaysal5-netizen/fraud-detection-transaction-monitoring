"use client";

import { useCallback, useEffect, useState } from "react";
import {
  api,
  formatWhen,
  SEVERITY_COLOR,
  type Alert,
  type AlertSeverity,
  type AlertStatus,
} from "@/lib/api";
import { Badge, Card, PageTitle, Spinner } from "@/components/ui";
import { toAlertShape, useAlertStream } from "@/lib/sse";

const SEVERITIES: (AlertSeverity | "")[] = ["", "critical", "high", "medium", "low"];
const STATUSES: (AlertStatus | "")[] = ["", "open", "in_progress", "escalated", "resolved", "false_positive"];

export function AlertsConsole({ token }: { token: string }) {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [severity, setSeverity] = useState<AlertSeverity | "">("");
  const [status, setStatus] = useState<AlertStatus | "">("");
  const [error, setError] = useState<string | null>(null);
  const { live } = useAlertStream();

  const load = useCallback(async () => {
    setError(null);
    try {
      setAlerts(await api.alerts(token, status || undefined, severity || undefined));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load alerts");
    }
  }, [token, status, severity]);

  useEffect(() => {
    load();
  }, [load]);

  const resolve = async (id: string, to: AlertStatus) => {
    setAlerts((prev) =>
      prev?.map((a) => (a.id === id ? { ...a, status: to } : a)) ?? prev,
    );
    try {
      await api.updateAlert(token, id, to, to === "false_positive" ? "reviewed as false positive" : "investigated and closed");
      await load();
    } catch {
      await load();
    }
  };

  const merged = useCallback(
    (list: Alert[]) => {
      const liveIds = new Set(live.map((l) => l.alert_id));
      const attached = alertFilter(live.map(toAlertShape));
      return [...attached, ...list.filter((a) => !liveIds.has(a.id))];
    },
    [live],
  );

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (alerts === null) return <Spinner />;

  const rows = merged(alerts);

  return (
    <div className="flex flex-col gap-5">
      <PageTitle
        title="Alert console"
        subtitle="Investigate transactions flagged by the rule engine and ML fusion."
      />

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2 text-zinc-600">
          Severity
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as AlertSeverity | "")}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-zinc-900"
          >
            {SEVERITIES.map((s) => (
              <option key={s || "all"} value={s}>
                {s || "all"}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-zinc-600">
          Status
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as AlertStatus | "")}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-zinc-900"
          >
            {STATUSES.map((s) => (
              <option key={s || "all"} value={s}>
                {s || "all"}
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={load}
          className="rounded-lg border border-zinc-300 px-3 py-1.5 text-zinc-700 hover:bg-zinc-50"
        >
          Refresh
        </button>
        <span className="text-xs text-zinc-400">{rows.length} shown</span>
      </div>

      <div className="flex flex-col gap-3">
        {rows.length === 0 && (
          <Card className="text-center text-sm text-zinc-500">
            No alerts match the current filters.
          </Card>
        )}
        {rows.map((a) => (
          <Card key={a.id} className="flex flex-col gap-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Badge className={SEVERITY_COLOR[a.severity]}>{a.severity}</Badge>
                <span className="font-mono text-sm font-medium text-zinc-900">{a.ref_no}</span>
                <Badge className="bg-zinc-100 text-zinc-600">{a.status}</Badge>
                <span className="text-xs text-zinc-500">{formatWhen(a.created_at)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">
                  risk {a.risk_score}
                </span>
                {a.status === "open" && (
                  <>
                    <button
                      onClick={() => resolve(a.id, "in_progress")}
                      className="rounded-lg border border-zinc-300 px-2.5 py-1 text-xs text-zinc-700 hover:bg-zinc-50"
                    >
                      Triage
                    </button>
                    <button
                      onClick={() => resolve(a.id, "false_positive")}
                      className="rounded-lg bg-emerald-600 px-2.5 py-1 text-xs text-white hover:bg-emerald-700"
                    >
                      False positive
                    </button>
                  </>
                )}
              </div>
            </div>
            <div className="flex flex-col gap-1 text-sm text-zinc-700">
              <p>{a.description}</p>
              <p className="text-xs text-zinc-500">
                type <span className="font-mono">{a.alert_type}</span>
                {a.rule_code && <> · rule <span className="font-mono">{a.rule_code}</span></>}
                {a.resolution_reason && <> · {a.resolution_reason}</>}
              </p>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function alertFilter(list: Alert[]): Alert[] {
  const seen = new Set<string>();
  return list.filter((a) => {
    if (seen.has(a.id)) return false;
    seen.add(a.id);
    return true;
  });
}