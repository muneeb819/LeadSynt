"use client";

import Link from "next/link";
import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/state/auth-context";
import { useTheme } from "@/hooks/useTheme";
import { Badge } from "@/components/ui/Badge";
import { timeAgo } from "@/utils/format";
import type { NotificationOut } from "@/types/api";

export function Topbar() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const { data, refresh } = useApi<{
    items: NotificationOut[];
    pagination: { total: number };
  }>(
    () => (user ? "/notifications?unread_only=true" : "/notifications?unread_only=true"),
    [user],
  );
  const unread = data?.pagination?.total ?? 0;
  const initials = (user?.full_name || "?")
    .split(" ")
    .map((s) => s[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-4 border-b border-zinc-800/80 bg-zinc-950/80 px-4 backdrop-blur sm:px-6">
      <div className="flex items-center gap-3 lg:hidden">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-xs font-bold text-white">
            L
          </div>
          <span className="text-sm font-semibold text-zinc-100">LeadSynt</span>
        </Link>
      </div>
      <div className="hidden items-center gap-2 text-xs text-zinc-500 lg:flex">
        <span className="h-2 w-2 rounded-full bg-emerald-500" />
        Live · connected to API
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={toggle}
          className="rounded-lg p-2 text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
          aria-label="Toggle theme"
          title="Toggle dark/light"
        >
          {theme === "dark" ? "☾" : "☀"}
        </button>

        <div className="relative">
          <button
            onClick={() => {
              setOpen((v) => !v);
              refresh();
            }}
            className="relative rounded-lg p-2 text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
            aria-label="Notifications"
          >
            ✉
            {unread > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white">
                {unread > 9 ? "9+" : unread}
              </span>
            )}
          </button>
          {open && (
            <div className="absolute right-0 mt-2 w-80 rounded-xl border border-zinc-800 bg-zinc-950 p-2 shadow-2xl">
              <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                Notifications
              </p>
              <div className="max-h-80 overflow-y-auto">
                {data?.items?.length ? (
                  data.items.map((n) => (
                    <div key={n.id} className="rounded-lg px-2 py-2 hover:bg-white/5">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-xs font-medium text-zinc-200">{n.title}</p>
                        <Badge tone={n.type === "HANDOVER" ? "violet" : "zinc"}>{n.type}</Badge>
                      </div>
                      {n.body && <p className="mt-0.5 line-clamp-2 text-[11px] text-zinc-500">{n.body}</p>}
                      <p className="mt-1 text-[10px] text-zinc-600">{timeAgo(n.created_at)}</p>
                    </div>
                  ))
                ) : (
                  <p className="px-2 py-6 text-center text-xs text-zinc-600">No unread notifications</p>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="ml-1 flex items-center gap-2.5 border-l border-zinc-800 pl-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-zinc-700 to-zinc-800 text-[11px] font-semibold text-zinc-200">
            {initials}
          </div>
          <div className="hidden sm:block">
            <p className="text-xs font-medium text-zinc-200">{user?.full_name}</p>
            <p className="text-[10px] text-zinc-500">{user?.roles?.join(", ")}</p>
          </div>
          <button
            onClick={logout}
            className="rounded-md px-2 py-1 text-[11px] text-zinc-500 hover:bg-white/5 hover:text-zinc-200"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
