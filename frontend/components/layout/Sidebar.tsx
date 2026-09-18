"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/utils/cn";
import { Logo } from "./Logo";

const NAV: { section: string; items: { href: string; label: string; icon: string }[] }[] = [
  {
    section: "Core",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: "◫" },
      { href: "/tickets", label: "Tickets", icon: "⬒" },
      { href: "/leads", label: "Leads", icon: "➤" },
      { href: "/contacts", label: "Contacts", icon: "👤" },
      { href: "/companies", label: "Companies", icon: "🏢" },
    ],
  },
  {
    section: "Intelligence",
    items: [
      { href: "/agents", label: "AI Agents", icon: "✦" },
      { href: "/qa", label: "QA Master", icon: "✓" },
      { href: "/analytics", label: "Analytics", icon: "📈" },
      { href: "/sources", label: "Sources", icon: "⇄" },
    ],
  },
  {
    section: "Pipeline",
    items: [
      { href: "/outreach", label: "Outreach", icon: "✉" },
      { href: "/conversations", label: "Conversations", icon: "💬" },
      { href: "/deals", label: "Deals", icon: "💼" },
      { href: "/marketplace", label: "Marketplace", icon: "▦" },
    ],
  },
  {
    section: "Platform",
    items: [
      { href: "/settings", label: "Settings", icon: "⚙" },
      { href: "/admin", label: "Admin", icon: "⛨" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-zinc-800/80 bg-zinc-950/80 backdrop-blur lg:flex">
      <Link href="/dashboard" className="flex items-center px-5 py-5">
        <Logo variant="master" className="h-9 w-auto" />
      </Link>
      <nav className="flex-1 overflow-y-auto px-3 pb-6">
        {NAV.map((group) => (
          <div key={group.section} className="mb-4">
            <p className="px-2 pb-1.5 pt-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-600">
              {group.section}
            </p>
            {group.items.map((item) => {
              const active = pathname?.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "mb-0.5 flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors",
                    active
                      ? "bg-indigo-500/10 text-indigo-300 ring-1 ring-inset ring-indigo-500/20"
                      : "text-zinc-400 hover:bg-white/5 hover:text-zinc-200",
                  )}
                >
                  <span className="w-4 text-center text-xs opacity-80">{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="border-t border-zinc-800/80 px-5 py-3">
        <p className="text-[10px] text-zinc-600">
          LeadSynt v0.1.0 · foundation
        </p>
      </div>
    </aside>
  );
}
