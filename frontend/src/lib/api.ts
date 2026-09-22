import { ApiError } from "@/lib/errors";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type Role = "customer" | "analyst" | "admin";

export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  two_factor_enabled: boolean;
  created_at: string;
}

export interface Account {
  id: string;
  user_id: string;
  account_number: string;
  account_type: "checking" | "savings";
  currency: string;
  balance: number;
  status: "active" | "frozen" | "closed";
  opened_at: string;
  account_age_days: number;
}

export interface Transaction {
  id: string;
  txn_ref: string;
  account_id: string;
  txn_type: "deposit" | "withdrawal" | "transfer" | "payment" | "refund";
  amount: number;
  currency: string;
  status: "pending" | "approved" | "rejected" | "flagged";
  risk_score: number | null;
  decision_reason: unknown[] | null;
  channel: "web" | "mobile" | "atm" | "api";
  city: string | null;
  country: string | null;
  created_at: string;
}

export interface TxnDecision {
  transaction: Transaction;
  risk_score: number;
  status: Transaction["status"];
  decision_reasons: { severity: string; code: string; message: string }[];
  ml_probability: number | null;
}

export type AlertSeverity = "low" | "medium" | "high" | "critical";
export type AlertStatus = "open" | "in_progress" | "escalated" | "resolved" | "false_positive";

export interface Alert {
  id: string;
  ref_no: string;
  account_id: string;
  user_id: string | null;
  transaction_id: string | null;
  severity: AlertSeverity;
  status: AlertStatus;
  alert_type: string;
  rule_code: string | null;
  risk_score: number;
  description: string;
  assignee_id: string | null;
  created_at: string;
  updated_at: string | null;
  resolved_at: string | null;
  resolution_reason: string | null;
}

export interface Overview {
  users: number;
  accounts: number;
  transactions: number;
  flagged: number;
  rejected: number;
  open_alerts: number;
  detection_rate: number;
}

interface AuthStore {
  token: string;
  user: User;
}

function readToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("fds.auth");
    return raw ? (JSON.parse(raw) as AuthStore).token : null;
  } catch {
    return null;
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const t = token ?? readToken();
  if (t) headers["Authorization"] = `Bearer ${t}`;

  const res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, cache: "no-store" });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new ApiError(res.status, body?.detail ?? `Request failed (${res.status})`);
  }
  return body as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; refresh_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  register: (data: { email: string; username: string; full_name: string; password: string }) =>
    request<{ access_token: string; refresh_token: string; user: User }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  accounts: (token?: string) => request<Account[]>("/accounts", {}, token),
  transactions: (token?: string) => request<Transaction[]>("/transactions?limit=30", {}, token),
  createTransaction: (token: string, payload: Record<string, unknown>) =>
    request<TxnDecision>("/transactions", { method: "POST", body: JSON.stringify(payload) }, token),
  alerts: (token: string, status?: AlertStatus, severity?: AlertSeverity) => {
    const q = new URLSearchParams();
    if (status) q.set("status", status);
    if (severity) q.set("severity", severity);
    const qs = q.toString() ? `?${q}` : "";
    return request<Alert[]>("/alerts" + qs, {}, token);
  },
  updateAlert: (token: string, id: string, status: AlertStatus, resolution_reason = "") =>
    request<Alert>(
      `/alerts/${id}`,
      { method: "PATCH", body: JSON.stringify({ status, resolution_reason }) },
      token,
    ),
  overview: (token: string) => request<Overview>("/admin/stats/overview", {}, token),
  transactionTrend: (token: string, days = 14) =>
    request<{ labels: string[]; values: number[] }>(
      `/admin/stats/transaction-trend?days=${days}`,
      {},
      token,
    ),
  riskDistribution: (token: string) =>
    request<{ buckets: string[]; counts: Record<string, number> }>(
      "/admin/stats/risk-distribution",
      {},
      token,
    ),
  volume: (token: string, days = 14) =>
    request<{ labels: string[]; values: number[] }>(`/reports/volume?days=${days}`, {}, token),
  fraudTrends: (token: string, days = 14) =>
    request<{ labels: string[]; approved: number[]; flagged: number[]; rejected: number[] }>(
      `/reports/fraud-trends?days=${days}`,
      {},
      token,
    ),
  modelMetrics: (token: string) =>
    request<{
      available: boolean;
      version?: string;
      trained_at?: string;
      metrics?: Record<string, number>;
      threshold?: number;
    }>("/admin/model-metrics", {}, token),
  rules: (token: string) =>
    request<Rule[]>("/admin/rules?limit=100", {}, token),
  toggleRule: (token: string, id: string, active: boolean) =>
    request<Rule>(`/admin/rules/${id}?active=${active}`, { method: "PATCH" }, token),
};

export interface Rule {
  id: string;
  code: string;
  name: string;
  severity: string;
  weight: number;
  is_active: boolean;
  params: Record<string, unknown>;
}

export function formatMoney(n: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(n);
}

export function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString();
}

export const SEVERITY_COLOR: Record<AlertSeverity, string> = {
  low: "bg-sky-100 text-sky-700",
  medium: "bg-amber-100 text-amber-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

export const STATUS_COLOR: Record<string, string> = {
  approved: "bg-emerald-100 text-emerald-700",
  flagged: "bg-amber-100 text-amber-700",
  rejected: "bg-red-100 text-red-700",
  pending: "bg-zinc-100 text-zinc-600",
};