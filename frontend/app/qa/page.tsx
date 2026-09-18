"use client";

import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { runQaSweep, listQaRuns, listQaFindings } from "@/services/qa";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge, SeverityBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingRow, EmptyState } from "@/components/ui/Feedback";
import { useAuth } from "@/state/auth-context";
import { formatDate } from "@/utils/format";
import { ApiClientError } from "@/lib/api-client";
import type { Envelope, QaFinding, QaRun } from "@/types/api";

export default function QaPage() {
  const { hasPermission } = useAuth();
  const [sweeping, setSweeping] = useState(false);
  const [sweepResult, setSweepResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const runs = useApi<Envelope<QaRun[]>>("/qa/runs?limit=10");
  const findings = useApi<Envelope<QaFinding[]>>("/qa/findings?limit=50");

  const sweep = async () => {
    setSweeping(true);
    setError(null);
    setSweepResult(null);
    try {
      const res = await runQaSweep();
      setSweepResult(res.data.summary);
      runs.refresh();
      findings.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sweep failed");
    } finally {
      setSweeping(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="QA Master"
        description="Continuous quality inspection — findings with severity, evidence and root-cause hypotheses"
        actions={
          hasPermission("qa:run") && (
            <Button onClick={sweep} disabled={sweeping}>
              {sweeping ? "Sweeping…" : "▶ Run QA sweep"}
            </Button>
          )
        }
      />

      {sweepResult && (
        <div className="mb-4 rounded-lg bg-emerald-500/10 px-4 py-3 text-xs text-emerald-400 ring-1 ring-inset ring-emerald-500/20">
          {sweepResult}
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-lg bg-rose-500/10 px-4 py-3 text-xs text-rose-400 ring-1 ring-inset ring-rose-500/20">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Open findings" subtitle="Latest first — every finding cites concrete evidence" />
          {findings.loading ? (
            <LoadingRow />
          ) : findings.error ? (
            <ErrorState message={findings.error} />
          ) : !findings.data?.data?.length ? (
            <EmptyState title="No findings" hint="Run a sweep — a healthy system produces no findings." />
          ) : (
            <div className="divide-y divide-zinc-800/60">
              {findings.data.data.map((f) => (
                <div key={f.id} className="px-5 py-4">
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={f.severity} />
                    <Badge tone="zinc">{f.category}</Badge>
                    <span className="ml-auto text-[10px] text-zinc-600">{formatDate(f.created_at)}</span>
                  </div>
                  <p className="mt-2 text-sm font-medium text-zinc-200">{f.title}</p>
                  {f.description && <p className="mt-1 text-xs text-zinc-500">{f.description}</p>}
                  <div className="mt-2 grid gap-1.5 text-[11px] sm:grid-cols-2">
                    {f.root_cause_hypothesis && (
                      <p className="text-zinc-500"><span className="text-zinc-600">Root cause: </span>{f.root_cause_hypothesis}</p>
                    )}
                    {f.recommended_action && (
                      <p className="text-zinc-500"><span className="text-zinc-600">Action: </span>{f.recommended_action}</p>
                    )}
                    {f.test_recommendation && (
                      <p className="text-zinc-600">Test: {f.test_recommendation}</p>
                    )}
                    {f.evidence && (
                      <p className="truncate font-mono text-zinc-600">evidence: {JSON.stringify(f.evidence).slice(0, 140)}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="Sweep history" />
          {runs.loading ? (
            <LoadingRow />
          ) : runs.data ? (
            <div className="divide-y divide-zinc-800/60">
              {runs.data.data.map((r) => (
                <div key={r.id} className="px-5 py-3">
                  <div className="flex items-center justify-between">
                    <Badge tone={r.status === "COMPLETED" ? "green" : "amber"}>{r.status}</Badge>
                    <span className="text-[10px] text-zinc-600">{formatDate(r.started_at)}</span>
                  </div>
                  {r.summary && <p className="mt-1.5 text-xs text-zinc-500">{r.summary}</p>}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No sweeps yet" />
          )}
        </Card>
      </div>
    </div>
  );
}
