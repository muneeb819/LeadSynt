"use client";

import Link from "next/link";
import { useApi } from "@/hooks/useApi";
import { getDashboard } from "@/services/dashboard";
import { listTickets } from "@/services/tickets";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { Table, Td, Tr } from "@/components/ui/Table";
import { Badge, HealthBadge, StatusBadge } from "@/components/ui/Badge";
import { ErrorState, LoadingRow } from "@/components/ui/Feedback";
import { formatMoney, timeAgo } from "@/utils/format";
import type { DashboardData, Envelope, Page, Ticket } from "@/types/api";

const PIPELINE_ORDER = [
  "DISCOVERED", "INGESTED", "PROCESSING", "REVIEW_REQUIRED",
  "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED", "OUTREACH_READY",
  "OUTREACH_ACTIVE", "REPLIED", "HOT_LEAD", "AWAITING_HUMAN",
  "MEETING_BOOKED", "NEGOTIATION", "PROPOSAL_SENT", "WON",
];

export default function DashboardPage() {
  const { data, loading, error, refresh } = useApi<Envelope<DashboardData>>(
    "/analytics/dashboard",
  );
  const tickets = useApi<Envelope<Page<Ticket>>>("/tickets?page_size=6&sort=-created_at");

  if (loading) return <LoadingRow />;
  if (error) return <ErrorState message={error} />;
  if (!data) return null;
  const d = data.data;

  return (
    <div>
      <PageHeader
        title="Control Center"
        description={`Executive view · generated ${timeAgo(d.generated_at)}`}
        actions={
          <button
            onClick={refresh}
            className="rounded-lg border border-zinc-800 px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200"
          >
            ↻ Refresh
          </button>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <StatCard label="New 24h" value={d.kpis.new_tickets_24h} accent="indigo" />
        <StatCard label="Verified" value={d.kpis.verified_tickets} accent="emerald" />
        <StatCard label="Qualified" value={d.kpis.qualified_tickets} accent="cyan" />
        <StatCard label="Hot Leads" value={d.kpis.hot_leads} accent="rose" />
        <StatCard label="Replies" value={d.kpis.replies} accent="violet" />
        <StatCard label="Open Deals" value={d.kpis.open_deals} accent="amber" />
        <StatCard label="Won" value={d.kpis.won_deals} accent="emerald" />
        <StatCard label="Avg Lead Score" value={d.kpis.avg_lead_score} accent="indigo" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Pipeline by status" subtitle="Live ticket distribution" />
          <div className="p-4">
            <div className="flex h-44 items-end gap-1.5">
              {PIPELINE_ORDER.map((s) => {
                const v = d.pipeline_by_status[s] || 0;
                const max = Math.max(1, ...PIPELINE_ORDER.map((x) => d.pipeline_by_status[x] || 0));
                const pct = (v / max) * 100;
                const hot = ["HOT_LEAD", "WON"].includes(s);
                const warm = ["REPLIED", "QUALIFIED", "OUTREACH_ACTIVE"].includes(s);
                return (
                  <div key={s} className="group relative flex flex-1 flex-col items-center gap-1.5">
                    <span className="text-[10px] tabular-nums text-zinc-500">{v || ""}</span>
                    <div
                      className={`w-full rounded-t ${
                        hot ? "bg-rose-500/80" : warm ? "bg-violet-500/70" : "bg-indigo-500/50"
                      } transition-all group-hover:opacity-100 ${v ? "" : "opacity-30"}`}
                      style={{ height: `${Math.max(4, pct * 120)}px` }}
                    />
                    <span className="w-full truncate text-center text-[8px] uppercase tracking-wide text-zinc-600">
                      {s.replaceAll("_", " ").split(" ")[0]}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Platform health" subtitle="Connectors · AI · jobs" />
          <div className="space-y-3 p-4 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Connectors healthy</span>
              <Badge tone={d.health.connectors_healthy === d.health.connectors_total ? "green" : "amber"}>
                {d.health.connectors_healthy}/{d.health.connectors_total}
              </Badge>
            </div>
            {d.health.connectors.map((c) => (
              <div key={c.connector_id} className="flex items-center justify-between rounded-lg bg-zinc-950/50 px-3 py-2">
                <span className="font-mono text-xs text-zinc-300">{c.connector_id}</span>
                <HealthBadge health={c.health} />
              </div>
            ))}
            <div className="flex items-center justify-between border-t border-zinc-800/80 pt-3">
              <span className="text-zinc-400">AI runs failed</span>
              <Badge tone={d.health.ai_runs_failed ? "red" : "green"}>{d.health.ai_runs_failed}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Job runs failed</span>
              <Badge tone={d.health.job_runs_failed ? "red" : "green"}>{d.health.job_runs_failed}</Badge>
            </div>
          </div>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader
          title="Latest tickets"
          subtitle="Most recently ingested business signals"
          actions={
            <Link href="/tickets" className="text-xs font-medium text-indigo-400 hover:text-indigo-300">
              View all →
            </Link>
          }
        />
        {tickets.loading ? (
          <LoadingRow />
        ) : tickets.data ? (
          <Table headers={["Reference", "Status", "Sector", "Requirement", "Lead", "Budget", "Verified", "Age"]}>
            {tickets.data.data.items.map((t) => (
              <Tr key={t.id} onRowClick={() => (window.location.href = `/tickets/${t.id}`)}>
                <Td>
                  <span className="font-mono text-xs text-zinc-300">{t.reference}</span>
                </Td>
                <Td><StatusBadge status={t.status} /></Td>
                <Td className="text-xs">{t.market_sector || "—"}</Td>
                <Td className="max-w-[260px]">
                  <span className="line-clamp-1 text-xs text-zinc-400">{t.requirement || t.product || "—"}</span>
                </Td>
                <Td>
                  <span className="tabular-nums text-sm font-semibold text-indigo-300">{t.lead_score ?? "—"}</span>
                </Td>
                <Td className="text-xs tabular-nums">{formatMoney(t.budget, t.currency)}</Td>
                <Td><Badge tone={t.verification_status === "VERIFIED" ? "green" : "zinc"}>{t.verification_status}</Badge></Td>
                <Td className="text-xs text-zinc-500">{timeAgo(t.discovered_at || t.created_at)}</Td>
              </Tr>
            ))}
          </Table>
        ) : (
          <ErrorState message={tickets.error || "Failed to load tickets"} />
        )}
      </Card>
    </div>
  );
}
