"use client";

import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api-client";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Table, Td, Tr } from "@/components/ui/Table";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingRow, EmptyState } from "@/components/ui/Feedback";
import type { Envelope, Page, ContactOut, CompanyOut } from "@/types/api";

export interface ContactRow {
  id: string;
  full_name: string;
  title: string | null;
  work_email: string | null;
  phone: string | null;
  profile_url: string | null;
  company_id: string | null;
  locale: string | null;
}

export default function ContactsPage() {
  const [q, setQ] = useState("");
  const { data, loading, error } = useApi<Envelope<Page<ContactRow>>>(
    `/contacts?page_size=25${q ? `&q=${encodeURIComponent(q)}` : ""}`,
    [q],
  );

  return (
    <div>
      <PageHeader title="Contacts" description="Decision makers, buyers and sellers linked to tickets" />
      <Card>
        <div className="border-b border-zinc-800/80 px-4 py-3">
          <Input placeholder="Search name or email…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        </div>
        {loading ? (
          <LoadingRow />
        ) : error ? (
          <ErrorState message={error} />
        ) : !data?.data?.items?.length ? (
          <EmptyState title="No contacts found" />
        ) : (
          <Table headers={["Name", "Title", "Email", "Phone", "Profile"]}>
            {data.data.items.map((c) => (
              <Tr key={c.id}>
                <Td className="text-sm font-medium text-zinc-200">{c.full_name}</Td>
                <Td className="text-xs text-zinc-400">{c.title || "—"}</Td>
                <Td className="text-xs text-zinc-400">{c.work_email || "—"}</Td>
                <Td className="text-xs text-zinc-400">{c.phone || "—"}</Td>
                <Td className="text-xs">
                  {c.profile_url ? (
                    <a href={c.profile_url} target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline">
                      profile
                    </a>
                  ) : (
                    "—"
                  )}
                </Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
