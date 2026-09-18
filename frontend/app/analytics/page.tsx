"use client";

import { useApi } from "@/hooks/useApi";
import { getDashboard } from "@/services/dashboard";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { ErrorState, LoadingRow } from "@/components/ui/Feedback";
import type { Envelope } from "@/types/api";
import type { DashboardData } from "@/types/api";

const STATUS_COLORS: Record<string, string> = {
  DISCOVERED: "#71717a",
  INGESTED: "#71717a",
  PROCESSING: "#38bdf8",
  REVIEW_REQUIRED: "#f59e0b",
  VERIFICATION_PENDING: "#f59e0b",
  VERIFIED: "#10b981",
  QUALIFIED: "#10b981",
  OUTREACH_READY: "#22d3ee",
  OUTREACH_ACTIVE: "#22d3ee",
  REPLIED: "#a78bfa",
  HOT_LEAD: "#f43f5e",
  AWAITING_HUMAN: "#f59e0b",
  MEETING_BOOKED: "#a78bfa",
  NEGOTIATION: "#a78bfa",
  PROPOSAL_SENT: "#a78bfa",
  WON: "#10b981",
  LOST: "#52525b",
  DISQUALIFIED: "#52525b",
  DUPLICATE: "#f59e0b",
  EXPIRED: "#52525b",
  ARCHIVED: "#3f3f46",
};

export default function AnalyticsPage() {
  const { data, loading, error } = useApi<Envelope<DashboardData>>("/analytics/dashboard");

  if (loading) return <LoadingRow />;
  if (error) return <ErrorState message={error} />;
  if (!data) return null;
  const d = data.data;

  const entries = Object.entries(d.pipeline_by_status).filter(([, v]) => v > 0);
  const max = Math.max(1, ...entries.map(([, v]) => v));

  return (
    <div>
      <PageHeader title="Analytics" description="Pipeline analytics computed from live database data" />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Avg lead score" value={d.kpis.avg_lead_score} accent="indigo" />
        <StatCard label="Verification rate" value={`${d.kpis.new_tickets_24h ? Math.round((d.kpis.verified_tickets / Math.max(1, d.kpis.new_tickets_24h + d.kpis.qualified_tickets)) * 100) : 0}%`} accent="emerald" />
        <StatCard label="Reply zone" value={d.kpis.replies + d.kpis.hot_leads} accent="violet" />
        <StatCard label="Deal zone" value={d.kpis.open_deals + d.kpis.won_deals} accent="amber" />
      </div>

      <Card className="mt-4">
        <CardHeader title="Pipeline distribution" subtitle="All tickets by current status" />
        <div className="space-y-2.5 p-5">
          {entries.length === 0 && <p className="text-sm text-zinc-600">No data yet.</p>}
          {entries
            .sort((a, b) => b[1] - a[1])
            .map(([status, count]) => (
              <div key={status} className="flex items-center gap-3">
                <span className="w-44 truncate text-xs text-zinc-400">{status.replaceAll("_", " ")}</span>
                <div className="h-4 flex-1 overflow-hidden rounded bg-zinc-800/60">
                  <div
                    className="h-full rounded transition-all"
                    style={{ width: `${(count / max) * 100}%`, backgroundColor: STATUS_COLORS[status] || "#6366f1" }}
                  />
                </div>
                <span className="w-8 text-right text-xs tabular-nums text-zinc-300">{count}</span>
              </div>
            ))}
        </div>
      </Card>

      <Card className="mt-4">
        <CardHeader title="Data quality signals" subtitle="From the latest QA sweep counts" />
        <div className="grid grid-cols-2 gap-3 p-5 sm:grid-cols-4">
          <div className="rounded-lg bg-zinc-950/50 p-3 text-center">
            <p className="text-xl font-semibold text-zinc-100">{d.health.connectors_healthy}/{d.health.connectors_total}</p>
            <p className="mt-1 text-[11px] text-zinc-500">connectors healthy</p>
          </div>
          <div className="rounded-lg bg-zinc-950/50 p-3 text-center">
            <p className="text-xl font-semibold text-zinc-100">{d.health.ai_runs_failed}</p>
            <p className="mt-1 text-[11px] text-zinc-500">AI run failures</p>
          </div>
          <div className="rounded-lg bg-zinc-950/50 p-3 text-center">
            <p className="text-xl font-semibold text-zinc-100">{d.health.job_runs_failed}</p>
            <p className="mt-1 text-[11px] text-zinc-500">job failures</p>
          </div>
          <div className="rounded-lg bg-zinc-950/50 p-3 text-center">
            <p className="text-xl font-semibold text-zinc-100">{Object.keys(d.pipeline_by_status).length}</p>
            <p className="mt-1 text-[11px] text-zinc-500">statuses tracked</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
