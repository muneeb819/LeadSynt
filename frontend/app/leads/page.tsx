"use client";

import { useRouter } from "next/navigation";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api-client";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Table, Td, Tr } from "@/components/ui/Table";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { ErrorState, LoadingRow, EmptyState } from "@/components/ui/Feedback";
import { formatMoney, timeAgo } from "@/utils/format";
import type { Envelope, Page, Ticket } from "@/types/api";

export default function LeadsPage() {
  const router = useRouter();
  const { data, loading, error } = useApi<Envelope<Page<Ticket>>>("/leads?page_size=25", []);

  return (
    <div>
      <PageHeader
        title="Leads"
        description="Qualified tickets in the lead zone, ranked by lead score"
      />
      <Card>
        {loading ? (
          <LoadingRow />
        ) : error ? (
          <ErrorState message={error} />
        ) : !data?.data?.items?.length ? (
          <EmptyState title="No qualified leads yet" hint="Advance tickets through verification to QUALIFIED to see them here." />
        ) : (
          <Table headers={["Reference", "Status", "Prospect", "Company", "Sector", "Intent", "Lead", "Risk", "Budget", "Updated"]}>
            {data.data.items.map((t) => (
              <Tr key={t.id} onRowClick={() => router.push(`/tickets/${t.id}`)}>
                <Td><span className="font-mono text-xs text-zinc-300">{t.reference}</span></Td>
                <Td><StatusBadge status={t.status} /></Td>
                <Td className="text-xs">{t.contacts[0]?.full_name || "—"}</Td>
                <Td className="max-w-[180px] truncate text-xs text-zinc-400">{t.companies[0]?.legal_name || "—"}</Td>
                <Td className="text-xs text-zinc-400">{t.market_sector || "—"}</Td>
                <Td>
                  {t.intent_level && <Badge tone={t.intent_level === "CRITICAL" ? "red" : t.intent_level === "HIGH" ? "amber" : "zinc"}>{t.intent_level}</Badge>}
                </Td>
                <Td><span className="text-sm font-semibold tabular-nums text-indigo-300">{t.lead_score ?? "—"}</span></Td>
                <Td><span className="tabular-nums text-xs text-zinc-400">{t.risk_score ?? "—"}</span></Td>
                <Td className="text-xs tabular-nums text-zinc-400">{formatMoney(t.budget, t.currency)}</Td>
                <Td className="text-xs text-zinc-500">{timeAgo(t.last_activity_at || t.updated_at)}</Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
