"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL, type Alert, type AlertSeverity, type AlertStatus } from "@/lib/api";

export interface LiveAlert {
  alert_id: string;
  ref_no: string;
  account_id: string;
  severity: AlertSeverity;
  status: AlertStatus;
  risk_score: number;
  alert_type: string;
  description: string;
}

function streamUrl(): string {
  return API_BASE_URL.replace(/\/+$/, "") + "/stream/alerts";
}

export function useAlertStream() {
  const [live, setLive] = useState<LiveAlert[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const es = new EventSource(streamUrl());

    es.addEventListener("connected", () => setConnected(true));

    es.addEventListener("alert", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data) as LiveAlert;
        if (data.ref_no) {
          setLive((prev) => [data, ...prev].slice(0, 12));
        }
      } catch {
        /* ignore malformed frames */
      }
    });

    es.onerror = () => setConnected(false);

    return () => es.close();
  }, []);

  return { live, connected };
}

export function toAlertShape(a: LiveAlert): Alert {
  return {
    id: a.alert_id,
    ref_no: a.ref_no,
    account_id: a.account_id,
    user_id: null,
    transaction_id: null,
    severity: a.severity,
    status: a.status,
    alert_type: a.alert_type,
    rule_code: a.alert_type.startsWith("rule:") ? a.alert_type.slice(5) : null,
    risk_score: a.risk_score,
    description: a.description,
    assignee_id: null,
    created_at: new Date().toISOString(),
    updated_at: null,
    resolved_at: null,
    resolution_reason: null,
  };
}