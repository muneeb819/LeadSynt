"use client";

import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api-client";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingRow, EmptyState } from "@/components/ui/Feedback";
import { useAuth } from "@/state/auth-context";
import { formatDate } from "@/utils/format";
import { ApiClientError } from "@/lib/api-client";
import type { Envelope, SettingOut } from "@/types/api";

export default function SettingsPage() {
  const { hasPermission } = useAuth();
  const { data, loading, error, refresh } = useApi<Envelope<SettingOut[]>>("/settings");
  const [editing, setEditing] = useState<SettingOut | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const startEdit = (s: SettingOut) => {
    setEditing(s);
    setText(JSON.stringify(s.value, null, 2));
    setErr(null);
  };

  const save = async () => {
    if (!editing) return;
    setBusy(true);
    setErr(null);
    try {
      const parsed = JSON.parse(text);
      await api(`/settings/${editing.key}`, { method: "PUT", body: JSON.stringify({ value: parsed }) });
      setEditing(null);
      refresh();
    } catch (e) {
      setErr(e instanceof ApiClientError ? e.message : "Invalid JSON or permission denied");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Dynamic, admin-tunable configuration — no hardcoded values operators should control"
      />
      {loading ? (
        <LoadingRow />
      ) : error ? (
        <ErrorState message={error} />
      ) : !data?.data?.length ? (
        <EmptyState title="No settings" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.data.map((s) => (
            <Card key={s.key} className="p-5">
              <div className="flex items-center justify-between">
                <p className="font-mono text-sm text-zinc-200">{s.key}</p>
                {hasPermission("settings:write") && editing?.key !== s.key && (
                  <Button size="sm" variant="ghost" onClick={() => startEdit(s)}>
                    Edit
                  </Button>
                )}
              </div>
              {s.description && <p className="mt-1 text-xs text-zinc-500">{s.description}</p>}
              {editing?.key === s.key ? (
                <div className="mt-3 space-y-2">
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    rows={7}
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 font-mono text-xs text-zinc-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
                  />
                  {err && <p className="text-xs text-rose-400">{err}</p>}
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                    <Button size="sm" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save"}</Button>
                  </div>
                </div>
              ) : (
                <pre className="mt-3 overflow-x-auto rounded-lg bg-zinc-950/60 p-3 text-xs leading-relaxed text-zinc-400">
                  {JSON.stringify(s.value, null, 2)}
                </pre>
              )}
              <p className="mt-2 text-[10px] text-zinc-600">
                updated {s.updated_at ? formatDate(s.updated_at) : "at seed time"}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
