"use client";

import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api-client";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { Table, Td, Tr } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { ErrorState, LoadingRow, EmptyState } from "@/components/ui/Feedback";
import { useAuth } from "@/state/auth-context";
import { formatDate } from "@/utils/format";
import { ApiClientError } from "@/lib/api-client";
import type { AuditRow, Envelope, UserOut } from "@/types/api";

export default function AdminPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("users:manage");
  const canAudit = hasPermission("audit:read");
  const users = useApi<Envelope<UserOut[]>>("/users");
  const audit = useApi<Envelope<AuditRow[]>>("/admin/audit?limit=30");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "viewer" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api("/users", { method: "POST", body: JSON.stringify(form) });
      setCreateOpen(false);
      setForm({ email: "", full_name: "", password: "", role: "viewer" });
      users.refresh();
    } catch (ex) {
      setErr(ex instanceof ApiClientError ? ex.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  const deactivate = async (id: string) => {
    try {
      await api(`/users/${id}/deactivate`, { method: "POST" });
      users.refresh();
    } catch {
      /* surfaced via users list state */
    }
  };

  return (
    <div>
      <PageHeader
        title="Admin"
        description="User management + full audit trail — every important operation is recorded"
        actions={
          canManage && (
            <Button onClick={() => setCreateOpen(true)}>+ New user</Button>
          )
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Users" subtitle="RBAC: admin / manager / operator / viewer" />
          {!canManage && !canAudit ? (
            <EmptyState title="Insufficient permissions" hint="Admin or manager role required." />
          ) : users.loading ? (
            <LoadingRow />
          ) : users.error ? (
            <ErrorState message={users.error} />
          ) : (
            <Table headers={["Email", "Name", "Role", "Status", "Last login", ""]}>
              {users.data?.data?.map((u) => (
                <Tr key={u.id}>
                  <Td className="text-xs">{u.email}</Td>
                  <Td className="text-xs text-zinc-400">{u.full_name}</Td>
                  <Td><Badge tone="violet">{u.roles.join(", ")}</Badge></Td>
                  <Td><Badge tone={u.is_active ? "green" : "zinc"}>{u.is_active ? "ACTIVE" : "INACTIVE"}</Badge></Td>
                  <Td className="text-[11px] text-zinc-500">{u.last_login_at ? formatDate(u.last_login_at) : "never"}</Td>
                  <Td>
                    {canManage && u.is_active && u.roles[0] !== "admin" && (
                      <Button size="sm" variant="ghost" onClick={() => deactivate(u.id)}>
                        Deactivate
                      </Button>
                    )}
                  </Td>
                </Tr>
              ))}
            </Table>
          )}
        </Card>

        <Card>
          <CardHeader title="Audit trail" subtitle="Most recent audited operations" />
          {audit.loading ? (
            <LoadingRow />
          ) : audit.error ? (
            <ErrorState message={audit.error} />
          ) : !audit.data?.data?.length ? (
            <EmptyState title="No audit entries yet" />
          ) : (
            <div className="max-h-[480px] divide-y divide-zinc-800/60 overflow-y-auto">
              {audit.data.data.map((a) => (
                <div key={a.id} className="px-5 py-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge tone="blue">{a.action}</Badge>
                      <span className="text-[11px] text-zinc-600">{a.actor_type}</span>
                    </div>
                    <span className="text-[10px] text-zinc-600">{formatDate(a.timestamp)}</span>
                  </div>
                  {(a.before || a.after) && (
                    <p className="mt-1 truncate font-mono text-[10px] text-zinc-600">
                      {a.before ? `before ${JSON.stringify(a.before).slice(0, 60)} · ` : ""}
                      {a.after ? `after ${JSON.stringify(a.after).slice(0, 80)}` : ""}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create user">
        <form onSubmit={create} className="space-y-4">
          <Field label="Email">
            <Input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} required />
          </Field>
          <Field label="Full name">
            <Input value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} required />
          </Field>
          <Field label="Password" hint="Minimum 10 characters">
            <Input type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} required minLength={10} />
          </Field>
          <Field label="Role">
            <select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-200"
            >
              <option>viewer</option>
              <option>operator</option>
              <option>manager</option>
              <option>admin</option>
            </select>
          </Field>
          {err && <p className="text-xs text-rose-400">{err}</p>}
          <div className="flex justify-end gap-2 border-t border-zinc-800 pt-4">
            <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy}>{busy ? "Creating…" : "Create"}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
