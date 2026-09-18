"use client";

import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { listAgents, agentRuns } from "@/services/agents";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ErrorState, LoadingRow, EmptyState } from "@/components/ui/Feedback";
import { formatDate } from "@/utils/format";
import type { Agent, AgentRun } from "@/types/api";

export default function AgentsPage() {
  const { data, loading, error } = useApi<Agent[]>("/agents");
  const [selected, setSelected] = useState<Agent | null>(null);
  const runs = useApi<AgentRun[]>(
    () => (selected ? `/agents/${selected.id}/runs?limit=20` : ""),
    [selected?.id],
  );

  return (
    <div>
      <PageHeader
        title="AI Agents"
        description="Specialized agents — every run is recorded with confidence, cost and evidence"
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            {loading ? (
              <LoadingRow />
            ) : error ? (
              <ErrorState message={error} />
            ) : (
              <div className="divide-y divide-zinc-800/60">
                {(data || []).map((a) => (
                  <button
                    key={a.id}
                    onClick={() => setSelected(a)}
                    className={`flex w-full items-start justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-white/[0.03] ${
                      selected?.id === a.id ? "bg-indigo-500/5" : ""
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-zinc-100">{a.name}</p>
                        <Badge tone="zinc">v{a.version}</Badge>
                        <Badge tone={a.status === "ACTIVE" ? "green" : "zinc"}>{a.status}</Badge>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-zinc-500">{a.purpose}</p>
                      <p className="mt-1.5 text-[11px] text-zinc-600">
                        {a.total_runs} runs · ${a.total_cost_usd.toFixed(3)} total · tools: {a.allowed_tools.slice(0, 3).join(", ")}
                      </p>
                    </div>
                    <span className="font-mono text-[10px] text-zinc-600">{a.agent_id}</span>
                  </button>
                ))}
              </div>
            )}
          </Card>
        </div>

        <Card>
          <CardHeader
            title={selected ? `${selected.name} — recent runs` : "Run history"}
            subtitle={selected ? selected.agent_id : "Select an agent"}
          />
          <div className="p-4">
            {!selected ? (
              <EmptyState title="Select an agent" hint="Run history, confidence, cost and errors appear here." />
            ) : runs.loading ? (
              <LoadingRow />
            ) : !runs.data?.length ? (
              <EmptyState title="No runs yet" hint="Agent runs appear after the scoring/QA engines or LLM integrations execute." />
            ) : (
              <div className="space-y-3">
                {runs.data.map((r) => (
                  <div key={r.id} className="rounded-lg bg-zinc-950/50 px-3 py-2.5">
                    <div className="flex items-center justify-between">
                      <Badge tone={r.status === "COMPLETED" ? "green" : r.status === "FAILED" ? "red" : "amber"}>
                        {r.status}
                      </Badge>
                      <span className="text-[10px] text-zinc-600">{formatDate(r.started_at)}</span>
                    </div>
                    <div className="mt-1.5 flex items-center gap-3 text-[11px] text-zinc-500">
                      <span>conf: {r.confidence ?? "—"}</span>
                      <span>cost: ${r.cost_usd?.toFixed(4) ?? "0"}</span>
                    </div>
                    {r.error && <p className="mt-1 text-[11px] text-rose-400">{r.error}</p>}
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
  );
}
