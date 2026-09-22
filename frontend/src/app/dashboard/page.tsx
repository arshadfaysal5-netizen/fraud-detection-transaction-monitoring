"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, formatMoney, formatWhen, STATUS_COLOR, type Account, type TxnDecision, type Transaction } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge, Card, PageTitle, Spinner, Stat } from "@/components/ui";
import { useAlertStream } from "@/lib/sse";

export default function DashboardPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();
  const { live } = useAlertStream();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user || !token) return <Spinner />;
  return user.role === "customer" ? (
    <CustomerDashboard token={token} liveAlerts={live} />
  ) : (
    <StaffDashboard token={token} isAdmin={user.role === "admin"} liveAlerts={live} />
  );
}

function CustomerDashboard({ token, liveAlerts }: { token: string; liveAlerts: unknown[] }) {
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [txns, setTxns] = useState<Transaction[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [a, t] = await Promise.all([api.accounts(token), api.transactions(token)]);
      setAccounts(a);
      setTxns(t);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const totalBalance = useMemo(() => accounts?.reduce((s, a) => s + a.balance, 0) ?? 0, [accounts]);
  const last24h = useMemo(() => {
    const cutoff = Date.now() - 24 * 3600 * 1000;
    return txns?.filter((t) => new Date(t.created_at).getTime() >= cutoff).length ?? 0;
  }, [txns]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!accounts || !txns) return <Spinner />;

  return (
    <div className="flex flex-col gap-6">
      <PageTitle
        title="My accounts"
        subtitle="Balances, recent activity and a quick way to simulate a transaction."
        right={
          liveAlerts.length > 0 ? (
            <Badge className="bg-red-100 text-red-700">{liveAlerts.length} live alerts</Badge>
          ) : undefined
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Total balance" value={formatMoney(totalBalance)} />
        <Stat label="Transactions (24h)" value={last24h} />
        <Stat label="Accounts" value={accounts.length} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">Accounts</h2>
          {accounts.map((a) => (
            <Card key={a.id} className="flex items-center justify-between gap-3">
              <div className="flex flex-col gap-1">
                <span className="font-mono text-sm text-zinc-900">•••• {a.account_number.slice(-4)}</span>
                <span className="text-xs capitalize text-zinc-500">{a.account_type}</span>
              </div>
              <div className="flex items-center gap-3">
                <Badge className="bg-zinc-100 text-zinc-600">{a.status}</Badge>
                <span className="text-base font-semibold text-zinc-900">
                  {formatMoney(a.balance, a.currency)}
                </span>
              </div>
            </Card>
          ))}
        </div>

        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">
            Recent transactions
          </h2>
          <div className="flex flex-col gap-2">
            {txns.slice(0, 10).map((t) => (
              <Card key={t.id} className="flex items-center justify-between gap-3 !py-3">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-zinc-900">
                    {t.txn_type} · {formatMoney(t.amount, t.currency)}
                  </span>
                  <span className="text-xs text-zinc-500">
                    {formatWhen(t.created_at)} · {t.city ?? "—"}
                    {t.risk_score !== null && <> · risk {t.risk_score}</>}
                  </span>
                </div>
                <Badge className={STATUS_COLOR[t.status]}>{t.status}</Badge>
              </Card>
            ))}
          </div>
        </div>
      </div>

      <NewTransaction token={token} accounts={accounts} onCreated={load} />
    </div>
  );
}

function NewTransaction({
  token,
  accounts,
  onCreated,
}: {
  token: string;
  accounts: Account[];
  onCreated: () => void;
}) {
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [txnType, setTxnType] = useState("withdrawal");
  const [amount, setAmount] = useState("250.00");
  const [channel, setChannel] = useState("mobile");
  const [device, setDevice] = useState("laptop-chrome");
  const [city, setCity] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TxnDecision | null>(null);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.createTransaction(token, {
        account_id: accountId,
        txn_type: txnType,
        amount: parseFloat(amount),
        channel,
        device_fingerprint: device,
        city: city || "London",
        country: "GB",
        latitude: 51.5074,
        longitude: -0.1278,
        ip_address: "88.70.12.34",
      });
      setResult(res);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transaction failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium uppercase tracking-widest text-zinc-500">
          Simulate a transaction
        </h2>
        <span className="text-xs text-zinc-400">Watch the risk engine decide in real time</span>
      </div>

      <form onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1 text-xs text-zinc-600">
          Account
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900"
          >
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                •••• {a.account_number.slice(-4)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-zinc-600">
          Type
          <select
            value={txnType}
            onChange={(e) => setTxnType(e.target.value)}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900"
          >
            {["withdrawal", "deposit", "payment", "transfer"].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-zinc-600">
          Amount (USD)
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-zinc-600">
          Channel
          <select
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900"
          >
            {["web", "mobile", "atm", "api"].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-zinc-600 lg:col-span-3">
          Device fingerprint
          <input
            value={device}
            onChange={(e) => setDevice(e.target.value)}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900"
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 lg:col-span-1"
        >
          {busy ? "Risk-scoring…" : "Submit"}
        </button>
      </form>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {result && (
        <div className="flex flex-col gap-3 justify-between rounded-lg border border-zinc-200 p-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <Badge className={STATUS_COLOR[result.status]}>{result.status}</Badge>
            <div className="flex flex-col">
              <span className="text-sm font-medium text-zinc-900">
                {result.transaction.txn_ref} · {formatMoney(result.transaction.amount)}
              </span>
              <span className="text-xs text-zinc-500">
                Risk {result.risk_score}/100
                {result.ml_probability !== null &&
                  ` · ML P(fraud) ${(result.ml_probability * 100).toFixed(1)}%`}
              </span>
            </div>
          </div>
          {result.decision_reasons.length > 0 && (
            <ul className="flex flex-wrap gap-1.5 text-xs">
              {result.decision_reasons.map((r, i) => (
                <li key={i} className="rounded-full bg-zinc-100 px-2 py-0.5 text-zinc-600">
                  {r.code}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Card>
  );
}

function StaffDashboard({
  token,
  isAdmin,
  liveAlerts,
}: {
  token: string;
  isAdmin: boolean;
  liveAlerts: unknown[];
}) {
  return (
    <div className="flex flex-col gap-6">
      <PageTitle
        title="Oversight dashboard"
        subtitle="Real-time alert stream for fraud analysts and administrators."
        right={
          liveAlerts.length > 0 ? (
            <Badge className="bg-red-100 text-red-700">{liveAlerts.length} live</Badge>
          ) : undefined
        }
      />
      {liveAlerts.slice(0, 4).map((a) => (
        <StaffLiveRow key={(a as { alert_id: string }).alert_id} a={a as never} />
      ))}
      <p className="text-sm text-zinc-500">
        Open the <span className="font-mono">Alerts</span> console to triage and resolve cases
        {isAdmin && ", or the Analytics page for aggregate charts"}.
      </p>
    </div>
  );
}

function StaffLiveRow({ a }: { a: { alert_id: string; ref_no: string; severity: string; risk_score: number; description: string } }) {
  return (
    <Card className="flex items-center justify-between gap-3">
      <div className="flex flex-col gap-0.5">
        <span className="text-sm font-medium text-zinc-900">
          <span className="font-mono">{a.ref_no}</span> · {a.description}
        </span>
        <span className="text-xs text-zinc-500">Live SSE · risk {a.risk_score}</span>
      </div>
      <Badge className="bg-red-100 text-red-700">{a.severity}</Badge>
    </Card>
  );
}