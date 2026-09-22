"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { AlertsConsole } from "@/components/AlertsConsole";
import { Spinner } from "@/components/ui";

export default function AlertsPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();
  const staff = user && user.role !== "customer";

  useEffect(() => {
    if (!loading && !staff) router.replace("/login");
  }, [loading, staff, router]);

  if (loading || !staff || !token) return <Spinner />;
  return <AlertsConsole token={token} />;
}