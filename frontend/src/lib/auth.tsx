"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, type User } from "@/lib/api";

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<User>;
  register: (data: {
    email: string;
    username: string;
    full_name: string;
    password: string;
  }) => Promise<User>;
  logout: () => void;
}

const TOKEN_KEY = "fds.auth";
const AuthContext = createContext<AuthState | null>(null);

interface Stored {
  token: string;
  user: User;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(TOKEN_KEY);
      if (raw) {
        const stored = JSON.parse(raw) as Stored;
        setToken(stored.token);
        setUser(stored.user);
      }
    } catch {
      localStorage.removeItem(TOKEN_KEY);
    } finally {
      setLoading(false);
    }
  }, []);

  const persist = useCallback((stored: Stored) => {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(stored));
    setToken(stored.token);
    setUser(stored.user);
  }, []);

  const login = useCallback(
    async (username: string, password: string) => {
      const res = await api.login(username, password);
      persist({ token: res.access_token, user: res.user });
      return res.user;
    },
    [persist],
  );

  const register = useCallback(
    async (data: { email: string; username: string; full_name: string; password: string }) => {
      const res = await api.register(data);
      persist({ token: res.access_token, user: res.user });
      return res.user;
    },
    [persist],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, token, loading, login, register, logout }),
    [user, token, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function requireRole(user: User | null, roles: User["role"][]): boolean {
  return !!user && roles.includes(user.role);
}