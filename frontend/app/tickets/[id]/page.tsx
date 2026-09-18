"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { transitionTicket, scoreTicket } from "@/services/tickets";
import { useAuth } from "@/state/auth-context";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge, StatusBadge, VerificationBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingRow } from "@/components/ui/Feedback";
import { formatDate, formatMoney } from "@/utils/format";
import { ApiClientError } from "@/lib/api-client";
import type { Envelope, TicketDetail } from "@/types/api";

// State-machine aware: which next statuses to offer.
const NEXT: Record<string, string[]> = {
  DISCOVERED: ["INGESTED"],
  INGESTED: ["PROCESSING", "REVIEW_REQUIRED"],
  PROCESSING: ["REVIEW_REQUIRED", "VERIFICATION_PENDING", "QUALIFIED", "DISQUALIFIED"],
  REVIEW_REQUIRED: ["PROCESSING", "VERIFICATION_PENDING", "QUALIFIED", "DISQUALIFIED"],
  VERIFICATION_PENDING: ["VERIFIED", "QUALIFIED", "DISQUALIFIED"],
  VERIFIED: ["QUALIFIED", "OUTREACH_READY", "DISQUALIFIED", "DUPLICATE"],
  QUALIFIED: ["OUTREACH_READY", "DISQUALIFIED"],
  OUTREACH_READY: ["OUTREACH_ACTIVE", "DISQUALIFIED"],
  OUTREACH_ACTIVE: ["REPLIED", "HOT_LEAD", "AWAITING_HUMAN", "DISQUALIFIED", "LOST"],
  REPLIED: ["HOT_LEAD", "AWAITING_HUMAN", "NEGOTIATION", "MEETING_BOOKED", "DISQUALIFIED"],
  HOT_LEAD: ["AWAITING_HUMAN", "MEETING_BOOKED", "NEGOTIATION", "DISQUALIFIED", "LOST"],
  AWAITING_HUMAN: ["MEETING_BOOKED", "NEGOTIATION", "OUTREACH_ACTIVE", "DISQUALIFIED", "LOST"],
  MEETING_BOOKED: ["NEGOTIATION", "PROPOSAL_SENT", "LOST"],
  NEGOTIATION: ["PROPOSAL_SENT", "WON", "LOST", "DISQUALIFIED"],
  PROPOSAL_SENT: ["WON", "LOST", "NEGOTIATION"],
  WON: ["ARCHIVED"],
  LOST: ["ARCHIVED"],
  DISQUALIFIED: ["ARCHIVED"],
  DUPLICATE: ["ARCHIVED"],
  EXPIRED: ["ARCHIVED"],
  ARCHIVED: [],
};

export default function TicketDetailPage() {
  const params = useParams<{ id: string }>();
  const { hasPermission } = useAuth();
  const { data, loading, error, refresh } = useApi<Envelope<TicketDetail>>(
    `/tickets/${params.id}`,
    [params.id],
  );
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (loading) return <LoadingRow />;
  if (error) return <ErrorState message={error} />;
  if (!data) return null;
  const t = data.data;

  const act = async (fn: () => Promise<unknown>, label: string) => {
    setBusy(true);
    setErrorBanner(null);
    try {
      await fn();
      refresh();
    } catch (e) {
      setErrorBanner(
        e instanceof ApiClientError ? `${label}: ${e.message}` : `${label}: unknown error`,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title={t.reference}
        description={`${t.type_name} · ${t.market_sector || "General"} · discovered ${formatDate(t.discovered_at || t.created_at)}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={t.status} />
            <VerificationBadge status={t.verification_status} />
            <Badge tone={t.duplicate_status === "UNIQUE" ? "green" : "amber"}>
              {t.duplicate_status.replaceAll("_", " ")}
            </Badge>
          </div>
        }
      />

      {errorBanner && (
        <div className="mb-4 rounded-lg bg-rose-500/10 px-4 py-3 text-xs text-rose-400 ring-1 ring-inset ring-rose-500/20">
          {errorBanner}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader title="Requirement" subtitle="Requirement + strategic context" />
            <div className="space-y-4 p-5">
              <p className="text-sm leading-relaxed text-zinc-300">
                {t.requirement || "No requirement captured."}
              </p>
              {t.pain_point && (
                <div className="rounded-lg bg-amber-500/5 px-4 py-3 ring-1 ring-inset ring-amber-500/15">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-amber-400">Pain point</p>
                  <p className="mt-1 text-sm text-zinc-300">{t.pain_point}</p>
                </div>
              )}
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
                {[
                  ["Product", t.product], ["Service", t.service],
                  ["Intent", t.intent_level], ["Urgency", t.urgency],
                  ["Budget", formatMoney(t.budget, t.currency)], ["Deal size", t.deal_size],
                  ["Location", t.location], ["Jurisdiction", t.jurisdiction], ["Timezone", t.timezone],
                  ["Domain", t.domain], ["Owner", t.owner_id ? "assigned" : "unassigned"],
                  ["Discovered by", t.discovered_by],
                ].map(([k, v]) => (
                  <div key={k as string}>
                    <dt className="text-[11px] uppercase tracking-wider text-zinc-600">{k}</dt>
                    <dd className="mt-0.5 text-zinc-300">{v || "—"}</dd>
                  </div>
                ))}
              </dl>
              {t.notes && (
                <div>
                  <p className="text-[11px] uppercase tracking-wider text-zinc-600">Notes</p>
                  <p className="mt-1 text-sm text-zinc-400">{t.notes}</p>
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Provenance" subtitle="Where this data came from — mandatory for every ticket" />
            <div className="space-y-2 p-5 text-sm">
              <Row k="Source platform" v={t.platform} />
              <Row k="Platform URL" v={t.platform_url} url />
              <Row k="Original URL" v={t.original_url} url />
              <Row k="Official website" v={t.official_website_url} url />
              <Row k="Discovered at" v={formatDate(t.discovered_at)} />
              <Row k="Published at" v={formatDate(t.published_at)} />
              <Row k="Last verified" v={formatDate(t.last_verified_at)} />
            </div>
          </Card>

          <Card>
            <CardHeader title="Verification history" subtitle="Immutable history — never overwritten" />
            <div className="divide-y divide-zinc-800/60">
              {(t.verification_history || []).length === 0 && (
                <p className="px-5 py-6 text-center text-xs text-zinc-600">No verification runs yet.</p>
              )}
              {(t.verification_history || []).map((v) => (
                <div key={v.id} className="flex items-start justify-between gap-4 px-5 py-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge tone="blue">{v.kind}</Badge>
                      <Badge tone={v.result === "VERIFIED" ? "green" : v.result === "FAILED" ? "red" : "amber"}>
                        {v.result}
                      </Badge>
                    </div>
                    {v.notes && <p className="mt-1 text-xs text-zinc-500">{v.notes}</p>}
                  </div>
                  <div className="text-right text-[11px] text-zinc-600">
                    <p>{formatDate(v.verified_at)}</p>
                    <p>by {v.verified_by || "—"}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Intelligence" />
            <div className="space-y-4 p-5">
              {([
                ["Lead", t.lead_score, "indigo"],
                ["Intent", t.intent_score, "violet"],
                ["Risk", t.risk_score, "rose"],
              ] as const).map(([label, v, color]) => (
                <div key={label}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="text-zinc-500">{label} score</span>
                    <span className="font-semibold tabular-nums text-zinc-200">{v ?? "—"}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-zinc-800">
                    <div
                      className={`h-full ${color === "indigo" ? "bg-indigo-500" : color === "violet" ? "bg-violet-500" : "bg-rose-500"}`}
                      style={{ width: `${v ?? 0}%` }}
                    />
                  </div>
                </div>
              ))}
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-500">Confidence</span>
                <span className="tabular-nums text-zinc-300">{t.confidence !== null ? `${Math.round(t.confidence * 100)}%` : "—"}</span>
              </div>
              {hasPermission("scoring:run") && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full"
                  disabled={busy}
                  onClick={() => act(() => scoreTicket(t.id), "Scoring")}
                >
                  ↻ Re-run scoring
                </Button>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="People & company" />
            <div className="space-y-3 p-5">
              {t.contacts.map((c) => (
                <div key={c.id} className="rounded-lg bg-zinc-950/50 px-3 py-2.5">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-zinc-200">{c.full_name}</p>
                    <Badge tone="violet">{c.role || "CONTACT"}</Badge>
                  </div>
                  {c.title && <p className="text-xs text-zinc-500">{c.title}</p>}
                  {c.work_email && <p className="mt-1 text-xs text-zinc-400">{c.work_email}</p>}
                  {c.phone && <p className="text-xs text-zinc-500">{c.phone}</p>}
                </div>
              ))}
              {t.companies.map((c) => (
                <div key={c.id} className="rounded-lg bg-zinc-950/50 px-3 py-2.5">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-zinc-200">{c.legal_name}</p>
                    <Badge tone={c.is_verified ? "green" : "zinc"}>
                      {c.is_verified ? "VERIFIED" : "UNVERIFIED"}
                    </Badge>
                  </div>
                  {c.domain && <p className="mt-1 text-xs text-zinc-500">{c.domain}</p>}
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Status transitions" subtitle="Controlled state machine — only valid moves offered" />
            <div className="p-4">
              {hasPermission("tickets:transition") ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    {(NEXT[t.status] || []).map((s) => (
                      <Button
                        key={s}
                        size="sm"
                        variant={s === "WON" ? "primary" : s === "LOST" || s === "DISQUALIFIED" ? "danger" : "secondary"}
                        disabled={busy}
                        onClick={() => act(() => transitionTicket(t.id, s), `Transition to ${s}`)}
                      >
                        → {s.replaceAll("_", " ")}
                      </Button>
                    ))}
                    {(NEXT[t.status] || []).length === 0 && (
                      <p className="text-xs text-zinc-600">Terminal status — no transitions available.</p>
                    )}
                  </div>
                  <p className="mt-3 text-[11px] leading-relaxed text-zinc-600">
                    Illegal transitions are rejected by the API (409) and never applied.
                    Replies trigger automatic handover + outreach pause.
                  </p>
                </>
              ) : (
                <p className="text-xs text-zinc-600">Your role cannot change ticket status.</p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v, url }: { k: string; v: string | null; url?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-xs text-zinc-600">{k}</span>
      <span className="text-right text-xs text-zinc-300">
        {v ? (
          url ? (
            <a href={v} target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline break-all">
              {v}
            </a>
          ) : (
            v
          )
        ) : (
          "—"
        )}
      </span>
    </div>
  );
}
