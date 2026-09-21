"use client";

import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import {
  agentAnalytics,
  agentModels,
  agentProviders,
  agentRuns,
  listAgents,
  runAgent,
} from "@/services/agents";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Input";
import { EmptyState, ErrorState, LoadingRow } from "@/components/ui/Feedback";
import { StatCard } from "@/components/ui/StatCard";
import { formatDate, formatMoney } from "@/utils/format";
import type {
  Agent,
  AgentAnalyticsItem,
  AgentAnalyticsResponse,
  AgentRun,
  AIModelOut,
  AIProviderOut,
} from "@/types/api";

function BudgetBar({ item }: { item: AgentAnalyticsItem }) {
  const { monthly_budget_usd, spent_this_month_usd, enforced } = item.budget;
  if (!enforced) {
    return (
      <p className="text-[11px] text-zinc-600">
        <span className="text-zinc-500">Budget:</span>{" "}
        <span className="text-zinc-400">unlimited</span>
      </p>
    );
  }
  const pct = Math.min(100, Math.round((spent_this_month_usd / monthly_budget_usd) * 100));
  const tone =
    pct >= 90 ? "bg-rose-500" : pct >= 60 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div>
      <div className="flex items-center justify-between text-[11px] text-zinc-500">
        <span>
          {formatMoney(spent_this_month_usd, "USD")} /{" "}
          {formatMoney(monthly_budget_usd, "USD")} MTD
        </span>
        <span
          className={
            pct >= 90
              ? "text-rose-400"
              : pct >= 60
                ? "text-amber-400"
                : "text-emerald-400"
          }
        >
          {pct}%
        </span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
        <div
          className={`h-full rounded-full ${tone}`}
          style={{ width: `${Math.max(4, pct)}%` }}
        />
      </div>
    </div>
  );
}

export default function AgentsPage() {
  const { data: agents, loading, error } = useApi<Agent[]>("/agents");
  const analytics = useApi<AgentAnalyticsResponse>("/agents/analytics");
  const providers = useApi<AIProviderOut[]>("/agents/providers");
  const models = useApi<AIModelOut[]>("/agents/models");
  const [selected, setSelected] = useState<Agent | null>(null);
  const runs = useApi<AgentRun[]>(
    () => (selected ? `/agents/${selected.id}/runs?limit=20` : ""),
    [selected?.id],
  );
  const [ticketId, setTicketId] = useState("");
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<AgentRun | null>(null);

  const overall = analytics.data?.overall;
  const analyticsByAgentId = new Map(
    (analytics.data?.items || []).map((i) => [i.agent.id, i]),
  );

  const handleRun = async () => {
    if (!selected) return;
    setRunning(true);
    setRunError(null);
    setLastRun(null);
    try {
      const res = await runAgent(selected.agent_id, {
        ticket_id: ticketId.trim() || undefined,
      });
      setLastRun(res.data);
      analytics.refresh();
      runs.refresh();
    } catch (e) {
      setRunError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="AI Agents"
        description="Specialized agents — every run is recorded with confidence, cost and evidence"
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Agents" value={overall?.agents ?? "—"} />
        <StatCard label="Total Runs" value={overall?.runs ?? "—"} />
        <StatCard
          label="Total Cost"
          value={overall ? formatMoney(overall.total_cost_usd, "USD") : "—"}
          sub={`${overall?.failed ?? 0} failed`}
        />
        <StatCard
          label="LLM Provider"
          value={overall?.llm_configured ? "Online" : "Offline"}
          sub={
            overall?.llm_configured
              ? "provider configured"
              : "deterministic engines active"
          }
          accent={overall?.llm_configured ? "emerald" : "amber"}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader
              title="Agent registry"
              subtitle="Select an agent to run it and inspect history"
            />
            {loading ? (
              <LoadingRow />
            ) : error ? (
              <ErrorState message={error} />
            ) : (
              <div className="divide-y divide-zinc-800/60">
                {(agents || []).map((a) => {
                  const analyticsItem = analyticsByAgentId.get(a.id);
                  return (
                    <button
                      key={a.id}
                      onClick={() => setSelected(a)}
                      className={`flex w-full flex-col gap-2 px-5 py-4 text-left transition-colors hover:bg-white/[0.03] ${
                        selected?.id === a.id ? "bg-indigo-500/5" : ""
                      }`}
                    >
                      <div className="flex w-full items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-zinc-100">
                              {a.name}
                            </p>
                            <Badge tone="zinc">v{a.version}</Badge>
                            <Badge tone={a.status === "ACTIVE" ? "green" : "zinc"}>
                              {a.status}
                            </Badge>
                          </div>
                          <p className="mt-1 line-clamp-2 text-xs text-zinc-500">
                            {a.purpose}
                          </p>
                          <p className="mt-1.5 text-[11px] text-zinc-600">
                            {analyticsItem?.runs.total ?? a.total_runs} runs ·{" "}
                            {formatMoney(
                              analyticsItem?.cost.total_usd ?? a.total_cost_usd,
                              "USD",
                            )}{" "}
                            total · tools:{" "}
                            {a.allowed_tools.slice(0, 3).join(", ")}
                          </p>
                        </div>
                        <span className="font-mono text-[10px] text-zinc-600">
                          {a.agent_id}
                        </span>
                      </div>
                      {analyticsItem && <BudgetBar item={analyticsItem} />}
                    </button>
                  );
                })}
              </div>
            )}
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader
              title={selected ? `Run ${selected.name}` : "Run an agent"}
              subtitle="Trigger a deterministic or LLM-backed run"
            />
            <div className="p-4">
              {!selected ? (
                <EmptyState
                  title="Select an agent"
                  hint="Pick an agent from the registry to trigger a run."
                />
              ) : (
                <div className="space-y-3">
                  <Field label="Ticket ID" hint="Optional — run without a ticket context.">
                    <Input
                      value={ticketId}
                      onChange={(e) => setTicketId(e.target.value)}
                      placeholder="ticket_..."
                      disabled={running}
                    />
                  </Field>
                  <Button
                    onClick={handleRun}
                    disabled={running}
                    className="w-full"
                  >
                    {running ? "Running…" : "Run agent"}
                  </Button>
                  {runError && (
                    <p className="text-[11px] text-rose-400">{runError}</p>
                  )}
                  {lastRun && (
                    <div className="rounded-lg bg-zinc-950/50 px-3 py-2.5">
                      <div className="flex items-center justify-between">
                        <Badge
                          tone={
                            lastRun.status === "COMPLETED"
                              ? "green"
                              : lastRun.status === "FAILED"
                                ? "red"
                                : "amber"
                          }
                        >
                          {lastRun.status}
                        </Badge>
                        <span className="text-[10px] text-zinc-600">
                          {formatDate(lastRun.started_at)}
                        </span>
                      </div>
                      <div className="mt-1.5 flex items-center gap-3 text-[11px] text-zinc-500">
                        <span>conf: {lastRun.confidence ?? "—"}</span>
                        <span>
                          cost: $
                          {lastRun.cost_usd?.toFixed(4) ?? "0"}
                        </span>
                      </div>
                      {lastRun.error && (
                        <p className="mt-1 text-[11px] text-rose-400">
                          {lastRun.error}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader
              title={selected ? `${selected.name} — recent runs` : "Run history"}
              subtitle={selected ? selected.agent_id : "Select an agent"}
            />
            <div className="p-4">
              {!selected ? (
                <EmptyState
                  title="Select an agent"
                  hint="Run history, confidence, cost and errors appear here."
                />
              ) : runs.loading ? (
                <LoadingRow />
              ) : !runs.data?.length ? (
                <EmptyState
                  title="No runs yet"
                  hint="Agent runs appear after the scoring engines or a manual run."
                />
              ) : (
                <div className="space-y-3">
                  {runs.data.map((r) => (
                    <div key={r.id} className="rounded-lg bg-zinc-950/50 px-3 py-2.5">
                      <div className="flex items-center justify-between">
                        <Badge
                          tone={
                            r.status === "COMPLETED"
                              ? "green"
                              : r.status === "FAILED"
                                ? "red"
                                : "amber"
                          }
                        >
                          {r.status}
                        </Badge>
                        <span className="text-[10px] text-zinc-600">
                          {formatDate(r.started_at)}
                        </span>
                      </div>
                      <div className="mt-1.5 flex items-center gap-3 text-[11px] text-zinc-500">
                        <span>conf: {r.confidence ?? "—"}</span>
                        <span>cost: ${r.cost_usd?.toFixed(4) ?? "0"}</span>
                      </div>
                      {r.error && (
                        <p className="mt-1 text-[11px] text-rose-400">{r.error}</p>
                      )}
                      {r.output && (
                        <p className="mt-1 truncate text-[11px] text-zinc-500">
                          {JSON.stringify(r.output).slice(0, 120)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="LLM providers"
            subtitle="Configured model providers for agent runs"
          />
          <div className="p-4">
            {providers.loading ? (
              <LoadingRow />
            ) : providers.error ? (
              <ErrorState message={providers.error} />
            ) : !providers.data?.length ? (
              <EmptyState title="No providers configured" />
            ) : (
              <div className="space-y-2.5">
                {providers.data.map((p) => (
                  <div
                    key={p.id}
                    className="flex items-center justify-between rounded-lg bg-zinc-950/50 px-3 py-2.5"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-zinc-100">
                          {p.name}
                        </p>
                        <Badge tone="zinc">{p.kind}</Badge>
                        {p.is_default && <Badge tone="cyan">default</Badge>}
                      </div>
                      <p className="mt-1 truncate font-mono text-[10px] text-zinc-600">
                        {p.base_url}
                      </p>
                    </div>
                    <div className="text-right">
                      <Badge tone={p.enabled ? "green" : "red"}>
                        {p.enabled ? "enabled" : "disabled"}
                      </Badge>
                      <p className="mt-1 text-[10px] text-zinc-600">
                        {p.model_count} models · key: {p.api_key_env || "—"}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Models"
            subtitle="Catalog used for cost estimation and budget caps"
          />
          <div className="p-4">
            {models.loading ? (
              <LoadingRow />
            ) : models.error ? (
              <ErrorState message={models.error} />
            ) : !models.data?.length ? (
              <EmptyState title="No models seeded" />
            ) : (
              <div className="space-y-2.5">
                {models.data.map((m) => (
                  <div
                    key={m.id}
                    className="flex items-center justify-between rounded-lg bg-zinc-950/50 px-3 py-2.5"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-zinc-100">
                        {m.display_name}
                      </p>
                      <p className="mt-1 truncate font-mono text-[10px] text-zinc-600">
                        {m.model_id}
                      </p>
                    </div>
                    <div className="text-right text-[10px] text-zinc-600">
                      <p>
                        ctx {m.context_window.toLocaleString()} · ${m.input_price_per_mtok.toFixed(2)}/M in · $
                        {m.output_price_per_mtok.toFixed(2)}/M out
                      </p>
                      <p className="mt-0.5">{m.provider_id || "—"}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}