import Link from "next/link";

const PHASES = [
  { phase: "Phase 1", title: "Core API · auth, users, accounts, transactions", done: true },
  { phase: "Phase 2", title: "Rule-based fraud engine · Redis velocity", done: true },
  { phase: "Phase 3", title: "Kafka event flow · alerts · investigation", done: true },
  { phase: "Phase 4", title: "ML pipeline (LightGBM/RandomForest) · risk fusion", done: true },
  { phase: "Phase 5", title: "Frontend dashboards · real-time feeds", done: true },
  { phase: "Phase 6", title: "Reports · analytics · hardening", done: true },
];

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      <section className="flex flex-col items-center gap-6 px-6 py-20 text-center">
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-zinc-900">
          Real-Time Fraud Detection & Transaction Monitoring System
        </h1>
        <p className="max-w-2xl text-base leading-7 text-zinc-600">
          A production-style simulation of a digital-banking monitoring platform. Transactions
          are risk-scored <strong>0–100</strong> in near real-time using a hybrid{" "}
          <strong>rule engine + ML classifier</strong>, streamed over <strong>Kafka</strong>,
          with velocity checks in <strong>Redis</strong> and a full alert / investigation
          workflow for analysts.
        </p>
        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="rounded-lg border border-zinc-300 px-5 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
          >
            Create customer account
          </Link>
        </div>
        <div className="flex flex-wrap justify-center gap-2 text-sm">
          {["Next.js", "FastAPI", "PostgreSQL", "Redis", "Kafka", "LightGBM", "Docker", "Recharts"].map(
            (t) => (
              <span key={t} className="rounded-full bg-zinc-100 px-3 py-1 text-zinc-700">
                {t}
              </span>
            ),
          )}
        </div>
      </section>

      <section className="mx-auto w-full max-w-3xl px-6 pb-20">
        <h2 className="mb-4 text-sm font-medium uppercase tracking-widest text-zinc-500">
          Roadmap
        </h2>
        <ol className="flex flex-col gap-2">
          {PHASES.map(({ phase, title, done }) => (
            <li
              key={phase}
              className="flex items-center gap-3 rounded-lg border border-zinc-200 px-4 py-3"
            >
              <span
                className={`h-2.5 w-2.5 shrink-0 rounded-full ${done ? "bg-emerald-500" : "bg-zinc-300"}`}
              />
              <span className="w-20 text-sm font-medium text-zinc-500">{phase}</span>
              <span className="text-sm text-zinc-800">{title}</span>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}