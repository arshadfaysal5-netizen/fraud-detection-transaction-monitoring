"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useAlertStream } from "@/lib/sse";

export function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const { live, connected } = useAlertStream();

  const staff = user && user.role !== "customer";

  const onLogout = () => {
    logout();
    router.replace("/");
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-6 py-3">
          <div className="flex items-center gap-6">
            <Link href="/" className="text-sm font-semibold text-zinc-900">
              FraudDesk
            </Link>
            <nav className="flex items-center gap-4 text-sm text-zinc-600">
              {user && (
                <>
                  <Link href="/dashboard" className="hover:text-zinc-900">
                    Dashboard
                  </Link>
                  {staff && (
                    <Link href="/alerts" className="hover:text-zinc-900">
                      Alerts
                    </Link>
                  )}
                  {user.role === "admin" && (
                    <Link href="/admin" className="hover:text-zinc-900">
                      Analytics
                    </Link>
                  )}
                </>
              )}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            {user && (
              <>
                <span
                  className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-zinc-300"}`}
                  title={connected ? "Live alert stream" : "Alert stream disconnected"}
                />
                {live.length > 0 && (
                  <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                    {live.length} live
                  </span>
                )}
                <span className="text-sm text-zinc-600">
                  {user.full_name}{" "}
                  <span className="text-zinc-400">({user.role})</span>
                </span>
                <button
                  onClick={onLogout}
                  className="text-sm text-zinc-500 hover:text-zinc-900"
                >
                  Sign out
                </button>
              </>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</main>
    </div>
  );
}