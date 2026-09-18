"use client";

import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Table, Td, Tr } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { ErrorState, LoadingRow, EmptyState } from "@/components/ui/Feedback";
import type { Envelope, Page, CompanyOut } from "@/types/api";

export default function CompaniesPage() {
  const [q, setQ] = useState("");
  const { data, loading, error } = useApi<Envelope<Page<CompanyOut>>>(
    `/companies?page_size=25${q ? `&q=${encodeURIComponent(q)}` : ""}`,
    [q],
  );

  return (
    <div>
      <PageHeader title="Companies" description="Organizations behind tickets, contacts and deals" />
      <Card>
        <div className="border-b border-zinc-800/80 px-4 py-3">
          <Input placeholder="Search name or domain…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        </div>
        {loading ? (
          <LoadingRow />
        ) : error ? (
          <ErrorState message={error} />
        ) : !data?.data?.items?.length ? (
          <EmptyState title="No companies found" />
        ) : (
          <Table headers={["Company", "Domain", "Industry", "Country", "Verified"]}>
            {data.data.items.map((c) => (
              <Tr key={c.id}>
                <Td className="text-sm font-medium text-zinc-200">{c.legal_name}</Td>
                <Td className="text-xs text-zinc-400">{c.domain || "—"}</Td>
                <Td className="text-xs text-zinc-400">{c.industry || "—"}</Td>
                <Td className="text-xs text-zinc-400">{c.country || "—"}</Td>
                <Td>
                  <Badge tone={c.is_verified ? "green" : "zinc"}>{c.is_verified ? "VERIFIED" : "UNVERIFIED"}</Badge>
                </Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
