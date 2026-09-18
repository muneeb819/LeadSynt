"use client";

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import type { MeOut } from "@/types/api";
import * as authService from "@/services/auth";

interface AuthState {
  user: MeOut | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (...roles: string[]) => boolean;
  hasPermission: (perm: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

const ROLE_PERMISSIONS: Record<string, string[] | "*"> = {
  admin: "*",
  manager: [
    "tickets:read", "tickets:write", "tickets:transition", "leads:read",
    "contacts:read", "contacts:write", "companies:read", "companies:write",
    "sources:read", "analytics:read", "agents:read", "agents:run",
    "qa:read", "qa:run", "notifications:read", "settings:read",
    "users:read", "audit:read", "verification:run", "scoring:run",
  ],
  operator: [
    "tickets:read", "tickets:write", "tickets:transition", "leads:read",
    "contacts:read", "contacts:write", "companies:read", "companies:write",
    "sources:read", "notifications:read", "verification:run", "scoring:run",
  ],
  viewer: [
    "tickets:read", "leads:read", "contacts:read", "companies:read",
    "sources:read", "analytics:read", "notifications:read",
  ],
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<MeOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authService.fetchMe().then((me) => {
      setUser(me);
      setLoading(false);
    });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await authService.login(email, password);
    const me = await authService.fetchMe();
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    authService.logout();
    setUser(null);
    window.location.href = "/login";
  }, []);

  const value = useMemo<AuthState>(() => ({
    user,
    loading,
    login,
    logout,
    hasRole: (...roles: string[]) =>
      !!user && user.roles.some((r) => roles.includes(r)),
    hasPermission: (perm: string) => {
      if (!user) return false;
      for (const role of user.roles) {
        const grants = ROLE_PERMISSIONS[role];
        if (grants === "*" || (Array.isArray(grants) && grants.includes(perm))) {
          return true;
        }
      }
      return false;
    },
  }), [user, loading, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
