"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  api,
  formatWhen,
  type Overview,
  type Rule,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, PageTitle, Spinner, Stat } from "@/components/ui";

const RISK_COLORS: Record<string, string> = {
  low: "#a1a1aa",
  medium: "#f59e0b",
  high: "#f97316",
  critical: "#ef4444",
};

export default function AdminPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && (!user || user.role !== "admin")) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user || user.role !== "admin" || !token) return <Spinner />;
  return <AdminAnalytics token={token} />;
}

function AdminAnalytics({ token }: { token: string }) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [trend, setTrend] = useState<{ labels: string[]; values: number[] } | null>(null);
  const [risk, setRisk] = useState<{ buckets: string[]; counts: Record<string, number> } | null>(null);
  const [fraud, setFraud] = useState<{ labels: string[]; approved: number[]; flagged: number[]; rejected: number[] } | null>(null);
  const [model, setModel] = useState<Awaited<ReturnType<typeof api.modelMetrics>> | null>(null);
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [o, t, r, f, m, ru] = await Promise.all([
        api.overview(token),
        api.transactionTrend(token, 14),
        api.riskDistribution(token),
        api.fraudTrends(token, 14),
        api.modelMetrics(token),
        api.rules(token),
      ]);
      setOverview(o);
      setTrend(t);
      setRisk(r);
      setFraud(f);
      setModel(m);
      setRules(ru ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load admin data");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleRule = async (id: string, active: boolean) => {
    setRules((prev) => prev?.map((r) => (r.id === id ? { ...r, is_active: active } : r)) ?? prev);
    await api.toggleRule(token, id, active).catch(() => undefined);
  };

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!overview || !trend || !risk || !fraud || !model || !rules) return <Spinner />;

  const trendData = trend.labels.map((l, i) => ({ day: l, count: trend.values[i] ?? 0 }));
  const riskData = risk.buckets
    .map((b) => ({ name: b, value: risk.counts[b] ?? 0 }))
    .filter((d) => d.value > 0);
  const fraudData = fraud.labels.map((l, i) => ({
    day: l,
    approved: fraud.approved[i] ?? 0,
    flagged: fraud.flagged[i] ?? 0,
    rejected: fraud.rejected[i] ?? 0,
  }));

  const volume = trend.values.reduce((s, v) => s + v, 0);

  return (
    <div className="flex flex-col gap-6">
      <PageTitle
        title="Analytics"
        subtitle="Aggregate fraud-detection metrics across the platform."
        right={
          <button onClick={load} className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50">
            Refresh
          </button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Transactions" value={overview.transactions} />
        <Stat label="Flagged" value={overview.flagged} hint={`${((overview.flagged / (overview.transactions || 1)) * 100).toFixed(1)}% of flow`} />
        <Stat label="Rejected" value={overview.rejected} />
        <Stat label="Detection rate" value={`${overview.detection_rate}%`} />
        <Stat label="Open alerts" value={overview.open_alerts} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="flex flex-col gap-3">
          <h3 className="text-sm font-medium uppercase tracking-widest text-zinc-500">Volume — 14d</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData} margin={{ left: -16, right: 8 }}>
                <defs>
                  <linearGradient id="vol" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#18181b" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#18181b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} tickMargin={6} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Area type="monotone" dataKey="count" stroke="#18181b" fill="url(#vol)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="flex flex-col gap-3">
          <h3 className="text-sm font-medium uppercase tracking-widest text-zinc-500">Risk distribution</h3>
          <div className="flex h-64 items-center justify-center">
            {riskData.length === 0 ? (
              <span className="text-sm text-zinc-400">No transactions yet</span>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={riskData} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="80%" paddingAngle={2}>
                    {riskData.map((d) => (
                      <Cell key={d.name} fill={RISK_COLORS[d.name] ?? "#a1a1aa"} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        <Card className="flex flex-col gap-3 lg:col-span-2">
          <h3 className="text-sm font-medium uppercase tracking-widest text-zinc-500">Decisions by day</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={fraudData} margin={{ left: -16, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} tickMargin={6} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="approved" stackId="d" fill="#10b981" />
                <Bar dataKey="flagged" stackId="d" fill="#f59e0b" />
                <Bar dataKey="rejected" stackId="d" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="flex flex-col gap-2 lg:col-span-2">
          <h3 className="text-sm font-medium uppercase tracking-widest text-zinc-500">ML model</h3>
          {model.available ? (
            <div className="flex flex-col gap-1 text-sm text-zinc-700">
              <p>
                <span className="text-zinc-500">version</span>{" "}
                <span className="font-mono">{model.version}</span>
              </p>
              <p>
                <span className="text-zinc-500">trained</span>{" "}
                {formatWhen(model.trained_at ?? "")}
              </p>
              <p>
                <span className="text-zinc-500">threshold</span>{" "}
                <span className="font-mono">{(model.threshold ?? 0).toFixed(4)}</span>
              </p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {Object.entries(model.metrics ?? {})
                  .filter(([k]) => k !== "optimal_threshold")
                  .map(([k, v]) => (
                    <p key={k} className="rounded-lg bg-zinc-50 px-3 py-2 text-xs">
                      <span className="block text-zinc-500">{k.replace("_", " ")}</span>
                      <span className="font-semibold text-zinc-900">
                        {typeof v === "number" ? v.toFixed(4) : v}
                      </span>
                    </p>
                  ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-zinc-500">No model artifact loaded.</p>
          )}
          <p className="mt-2 text-xs text-zinc-400">
            {volume} transactions scored by rule engine {">"} ML fusion.
          </p>
        </Card>

        <Card className="flex flex-col gap-2 lg:col-span-3">
          <h3 className="text-sm font-medium uppercase tracking-widest text-zinc-500">Rule engine</h3>
          <div className="flex flex-col">
            {rules.map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-3 border-b border-zinc-100 py-2 text-sm last:border-0">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-zinc-900">{r.code}</span>
                  <span className="text-zinc-600">{r.name}</span>
                  <span className="text-xs capitalize text-zinc-400">{r.severity} · w{r.weight}</span>
                </div>
                <button
                  onClick={() => toggleRule(r.id, !r.is_active)}
                  title="Toggle rule"
                  className={`relative h-5 w-9 rounded-full transition-colors ${r.is_active ? "bg-emerald-500" : "bg-zinc-300"}`}
                >
                  <span
                    className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${r.is_active ? "translate-x-[18px]" : "translate-x-0.5"}`}
                  />
                </button>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}