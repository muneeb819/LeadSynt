"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/state/auth-context";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Input";
import { Logo } from "@/components/layout/Logo";

export default function LoginPage() {
  const { login, user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) router.replace("/dashboard");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  const quickFill = (role: string) => {
    setEmail(role === "admin" ? "admin@leadsynt.io" : `${role}@leadsynt.io`);
    setPassword("LeadSynt-Dev-Only-2026");
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-4">
          <Logo variant="master" className="h-14 w-auto" />
          <div className="text-center">
            <p className="text-[11px] font-medium uppercase tracking-[0.3em] text-zinc-500">
              Global Revenue Architects
            </p>
            <p className="mt-1.5 text-sm text-zinc-500">
              Lead Intelligence · Discovery · CRM · QA
            </p>
          </div>
        </div>

        <form
          onSubmit={submit}
          className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 backdrop-blur"
        >
          <div className="space-y-4">
            <Field label="Email">
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@leadsynt.io"
                autoComplete="username"
                required
              />
            </Field>
            <Field label="Password">
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                autoComplete="current-password"
                required
              />
            </Field>
            {error && (
              <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400 ring-1 ring-inset ring-rose-500/20">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </div>

          <div className="mt-5 border-t border-zinc-800 pt-4">
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-zinc-600">
              Dev quick-fill (seeded users)
            </p>
            <div className="flex gap-2">
              {["admin", "operator", "viewer"].map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => quickFill(r)}
                  className="flex-1 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2 py-1.5 text-xs text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
        </form>

        <p className="mt-6 text-center text-[11px] leading-relaxed text-zinc-600">
          JWT-secured API · RBAC enforced · all actions audited.
          <br />
          Dev credentials are for local development only.
        </p>
      </div>
    </div>
  );
}
