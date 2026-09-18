"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Field, Input, Select, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { createTicket } from "@/services/tickets";
import { ApiClientError } from "@/lib/api-client";

export function NewTicketDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    type_code: "PROCUREMENT",
    market_sector: "",
    product: "",
    requirement: "",
    intent_level: "MEDIUM",
    urgency: "MONTH",
    budget: "",
    currency: "USD",
    location: "",
    company_name: "",
    company_domain: "",
    contact_name: "",
    contact_email: "",
    contact_phone: "",
    original_url: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await createTicket({
        type_code: form.type_code,
        market_sector: form.market_sector || null,
        product: form.product || null,
        requirement: form.requirement || null,
        intent_level: form.intent_level,
        urgency: form.urgency,
        budget: form.budget ? Number(form.budget) : null,
        currency: form.currency || null,
        location: form.location || null,
        company: form.company_name
          ? { legal_name: form.company_name, domain: form.company_domain || null }
          : null,
        contact: form.contact_name
          ? {
              full_name: form.contact_name,
              work_email: form.contact_email || null,
              phone: form.contact_phone || null,
            }
          : null,
        original_url: form.original_url || null,
        discovered_by: "manual",
      });
      setForm((f) => ({ ...f, market_sector: "", product: "", requirement: "", budget: "", location: "", company_name: "", company_domain: "", contact_name: "", contact_email: "", contact_phone: "", original_url: "" }));
      onCreated();
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 403) {
        setError("Your role does not allow creating tickets.");
      } else {
        setError(err instanceof Error ? err.message : "Failed to create ticket");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="New ticket" wide>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Type">
            <Select value={form.type_code} onChange={set("type_code")}>
              <option>PROCUREMENT</option>
              <option>RFP</option>
              <option>MARKET_OPPORTUNITY</option>
              <option>BUYER</option>
              <option>SELLER</option>
              <option>JOB</option>
              <option>GENERAL</option>
            </Select>
          </Field>
          <Field label="Market sector">
            <Input value={form.market_sector} onChange={set("market_sector")} placeholder="Manufacturing" />
          </Field>
          <Field label="Product / service">
            <Input value={form.product} onChange={set("product")} placeholder="CNC spindles" />
          </Field>
          <Field label="Intent level">
            <Select value={form.intent_level} onChange={set("intent_level")}>
              <option>LOW</option>
              <option>MEDIUM</option>
              <option>HIGH</option>
              <option>CRITICAL</option>
            </Select>
          </Field>
          <Field label="Urgency">
            <Select value={form.urgency} onChange={set("urgency")}>
              <option>NOW</option>
              <option>WEEK</option>
              <option>MONTH</option>
              <option>UNKNOWN</option>
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Budget">
              <Input type="number" min="0" value={form.budget} onChange={set("budget")} placeholder="50000" />
            </Field>
            <Field label="Currency">
              <Input value={form.currency} onChange={set("currency")} maxLength={8} />
            </Field>
          </div>
        </div>
        <Field label="Requirement">
          <Textarea value={form.requirement} onChange={set("requirement")} placeholder="What is needed, timeline, constraints…" />
        </Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Location">
            <Input value={form.location} onChange={set("location")} placeholder="Karachi, PK" />
          </Field>
          <Field label="Source URL (provenance)">
            <Input value={form.original_url} onChange={set("original_url")} placeholder="https://…" />
          </Field>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">Contact & company</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Company name">
              <Input value={form.company_name} onChange={set("company_name")} placeholder="Acme Industrial" />
            </Field>
            <Field label="Company domain">
              <Input value={form.company_domain} onChange={set("company_domain")} placeholder="acme-industrial.com" />
            </Field>
            <Field label="Contact name">
              <Input value={form.contact_name} onChange={set("contact_name")} placeholder="Jane Doe" />
            </Field>
            <Field label="Work email">
              <Input type="email" value={form.contact_email} onChange={set("contact_email")} placeholder="jane@acme.com" />
            </Field>
            <Field label="Phone">
              <Input value={form.contact_phone} onChange={set("contact_phone")} placeholder="+92 300 0000000" />
            </Field>
          </div>
        </div>
        {error && (
          <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400 ring-1 ring-inset ring-rose-500/20">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2 border-t border-zinc-800 pt-4">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create ticket"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
