"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useApi } from "@/hooks/useApi";
import { listTickets } from "@/services/tickets";
import type { TicketFilters } from "@/services/tickets";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Table, Td, Tr } from "@/components/ui/Table";
import { Badge, StatusBadge, VerificationBadge } from "@/components/ui/Badge";
import { Input, Select } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingRow, EmptyState } from "@/components/ui/Feedback";
import { NewTicketDialog } from "@/components/tickets/NewTicketDialog";
import { formatMoney, timeAgo } from "@/utils/format";
import { useAuth } from "@/state/auth-context";
import type { Envelope, Page, Ticket } from "@/types/api";

export default function TicketsPage() {
  const router = useRouter();
  const { hasPermission } = useAuth();
  const [filters, setFilters] = useState<
    TicketFilters & { page: number; page_size: number; sort: string }
  >({
    page: 1,
    page_size: 15,
    status: "",
    verification: "",
    q: "",
    sort: "-created_at",
  });
  const [newOpen, setNewOpen] = useState(false);
  const [search, setSearch] = useState("");

  const { data, loading, error, refresh } = useApi<Envelope<Page<Ticket>>>(listPath, [
    filters.page, filters.status, filters.verification, filters.sort, search,
  ]);

  function listPath() {
    const p = new URLSearchParams();
    p.set("page", String(filters.page));
    p.set("page_size", String(filters.page_size));
    if (filters.status) p.set("status", filters.status);
    if (filters.verification) p.set("verification", filters.verification);
    if (search) p.set("q", search);
    if (filters.sort) p.set("sort", filters.sort);
    return `/tickets?${p.toString()}`;
  }

  const pages = useMemo(
    () => data?.data?.pagination?.total_pages ?? 1,
    [data],
  );

  return (
    <div>
      <PageHeader
        title="Tickets"
        description="Central business object — every discovered opportunity, requirement and lead"
        actions={
          hasPermission("tickets:write") && (
            <Button onClick={() => setNewOpen(true)}>+ New ticket</Button>
          )
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800/80 px-4 py-3">
          <Input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setFilters((f) => ({ ...f, page: 1 }));
            }}
            placeholder="Search reference, product, requirement…"
            className="max-w-xs"
          />
          <Select
            value={filters.status || ""}
            onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value, page: 1 }))}
            className="w-auto"
          >
            <option value="">All statuses</option>
            {["DISCOVERED","INGESTED","PROCESSING","REVIEW_REQUIRED","VERIFICATION_PENDING","VERIFIED","QUALIFIED","OUTREACH_READY","OUTREACH_ACTIVE","REPLIED","HOT_LEAD","AWAITING_HUMAN","MEETING_BOOKED","NEGOTIATION","PROPOSAL_SENT","WON","LOST","DISQUALIFIED","DUPLICATE","EXPIRED"].map((s) => (
              <option key={s} value={s}>{s.replaceAll("_", " ")}</option>
            ))}
          </Select>
          <Select
            value={filters.verification || ""}
            onChange={(e) => setFilters((f) => ({ ...f, verification: e.target.value, page: 1 }))}
            className="w-auto"
          >
            <option value="">Any verification</option>
            <option value="VERIFIED">Verified</option>
            <option value="PENDING">Pending</option>
            <option value="FAILED">Failed</option>
            <option value="UNVERIFIED">Unverified</option>
          </Select>
          <Select
            value={filters.sort}
            onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value, page: 1 }))}
            className="w-auto"
          >
            <option value="-created_at">Newest first</option>
            <option value="-lead_score">Lead score ↓</option>
            <option value="-last_activity_at">Activity ↓</option>
            <option value="created_at">Oldest first</option>
          </Select>
          <span className="ml-auto text-xs text-zinc-500">
            {data?.data?.pagination?.total ?? 0} tickets
          </span>
        </div>

        {loading ? (
          <LoadingRow />
        ) : error ? (
          <ErrorState message={error} />
        ) : !data?.data?.items?.length ? (
          <EmptyState title="No tickets yet" hint="Create a ticket or run the dev_feed connector to ingest the first batch." />
        ) : (
          <Table headers={["Reference", "Status", "Type", "Prospect", "Company", "Sector", "Intent", "Lead", "Budget", "Verification", "Age"]}>
            {data.data.items.map((t) => (
              <Tr key={t.id} onRowClick={() => router.push(`/tickets/${t.id}`)}>
                <Td><span className="font-mono text-xs text-zinc-300">{t.reference}</span></Td>
                <Td><StatusBadge status={t.status} /></Td>
                <Td className="text-xs text-zinc-400">{t.type_code.replaceAll("_", " ")}</Td>
                <Td className="text-xs">{t.contacts[0]?.full_name || "—"}</Td>
                <Td className="max-w-[180px] truncate text-xs text-zinc-400">{t.companies[0]?.legal_name || "—"}</Td>
                <Td className="text-xs text-zinc-400">{t.market_sector || "—"}</Td>
                <Td>
                  {t.intent_level ? (
                    <Badge tone={t.intent_level === "CRITICAL" ? "red" : t.intent_level === "HIGH" ? "amber" : "zinc"}>
                      {t.intent_level}
                    </Badge>
                  ) : (
                    "—"
                  )}
                </Td>
                <Td>
                  <div className="flex items-center gap-2">
                    <span className="w-7 text-sm font-semibold tabular-nums text-indigo-300">{t.lead_score ?? "—"}</span>
                    <div className="h-1.5 w-14 overflow-hidden rounded-full bg-zinc-800">
                      <div className="h-full bg-indigo-500" style={{ width: `${t.lead_score ?? 0}%` }} />
                    </div>
                  </div>
                </Td>
                <Td className="text-xs tabular-nums text-zinc-400">{formatMoney(t.budget, t.currency)}</Td>
                <Td><VerificationBadge status={t.verification_status} /></Td>
                <Td className="text-xs text-zinc-500">{timeAgo(t.discovered_at || t.created_at)}</Td>
              </Tr>
            ))}
          </Table>
        )}

        <div className="flex items-center justify-between border-t border-zinc-800/80 px-4 py-3 text-xs text-zinc-500">
          <span>
            Page {filters.page} / {pages}
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" disabled={filters.page <= 1} onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}>
              ← Prev
            </Button>
            <Button variant="secondary" size="sm" disabled={filters.page >= pages} onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>
              Next →
            </Button>
          </div>
        </div>
      </Card>

      <NewTicketDialog open={newOpen} onClose={() => setNewOpen(false)} onCreated={() => { setNewOpen(false); refresh(); }} />
    </div>
  );
}
