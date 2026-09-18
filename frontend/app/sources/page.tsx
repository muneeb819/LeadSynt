"use client";

import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import {
  listSources, listConnectors, runConnector,
} from "@/services/sources";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge, HealthBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingRow, EmptyState } from "@/components/ui/Feedback";
import { useAuth } from "@/state/auth-context";
import { formatDate } from "@/utils/format";
import { ApiClientError } from "@/lib/api-client";
import type { ConnectorOut, Envelope, SourceOut } from "@/types/api";

export default function SourcesPage() {
  const { hasPermission } = useAuth();
  const sources = useApi<Envelope<SourceOut[]>>("/sources");
  const connectors = useApi<Envelope<ConnectorOut[]>>("/connectors");
  const [running, setRunning] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = async (key: string) => {
    setRunning(key);
    setMsg(null);
    setErr(null);
    try {
      const res = await runConnector(key);
      const d = res.data as Record<string, unknown>;
      setMsg(
        d.status === "COMPLETED"
          ? `${key}: found ${d.records_found} records, created ${d.tickets_created} new tickets (idempotent).`
          : `${key}: ${d.status} — ${String(d.reason ?? d.error ?? "")}`,
      );
      connectors.refresh();
    } catch (e) {
      setErr(e instanceof ApiClientError ? e.message : "Run failed");
    } finally {
      setRunning(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Sources & Connectors"
        description="Authorized channels only — no scraping, no CAPTCHA/paywall/anti-bot bypasses"
      />
      {msg && (
        <div className="mb-4 rounded-lg bg-emerald-500/10 px-4 py-3 text-xs text-emerald-400 ring-1 ring-inset ring-emerald-500/20">
          {msg}
        </div>
      )}
      {err && (
        <div className="mb-4 rounded-lg bg-rose-500/10 px-4 py-3 text-xs text-rose-400 ring-1 ring-inset ring-rose-500/20">
          {err}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Connectors" subtitle="Scheduled runs via Celery beat; on-demand runs in-process" />
          {connectors.loading ? (
            <LoadingRow />
          ) : connectors.data ? (
            <div className="divide-y divide-zinc-800/60">
              {connectors.data.data.map((c) => (
                <div key={c.id} className="px-5 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm text-zinc-200">{c.connector_id}</span>
                        <HealthBadge health={c.health} />
                        <Badge tone="zinc">{c.auth_method}</Badge>
                      </div>
                      <p className="mt-1 text-xs text-zinc-500">
                        {c.source_name} · schedule {c.schedule_cron || "—"} · rate {c.rate_limit_per_hour || "—"}/h
                      </p>
                      <p className="mt-0.5 text-[11px] text-zinc-600">
                        last success {formatDate(c.last_success_at)}
                        {c.last_error && <span className="text-rose-500"> · error: {c.last_error.slice(0, 80)}</span>}
                      </p>
                    </div>
                    {hasPermission("sources:run") && (
                      <Button size="sm" variant="secondary" disabled={running === c.connector_id} onClick={() => run(c.connector_id)}>
                        {running === c.connector_id ? "Running…" : "▶ Run"}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <ErrorState message={connectors.error || "Failed"} />
          )}
        </Card>

        <Card>
          <CardHeader title="Sources" subtitle="Authorized discovery channels" />
          {sources.loading ? (
            <LoadingRow />
          ) : sources.data ? (
            <div className="divide-y divide-zinc-800/60">
              {sources.data.data.map((s) => (
                <div key={s.id} className="px-5 py-4">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-zinc-200">{s.name}</p>
                    <Badge tone="blue">{s.kind}</Badge>
                    <Badge tone={s.is_active ? "green" : "zinc"}>{s.is_active ? "ACTIVE" : "INACTIVE"}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-zinc-500">{s.description || s.base_url || "—"}</p>
                  {s.compliance_notes && (
                    <p className="mt-1 text-[11px] text-emerald-500/80">🛡 {s.compliance_notes}</p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <ErrorState message={sources.error || "Failed"} />
          )}
        </Card>
      </div>
    </div>
  );
}
