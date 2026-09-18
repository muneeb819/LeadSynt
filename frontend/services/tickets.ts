import { api } from "@/lib/api-client";
import type { Envelope, Page, Ticket, TicketDetail } from "@/types/api";

export interface TicketFilters {
  page?: number;
  page_size?: number;
  status?: string;
  type_code?: string;
  verification?: string;
  duplicate_status?: string;
  market_sector?: string;
  q?: string;
  sort?: string;
}

export function ticketsUrl(f: TicketFilters = {}): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  }
  const qs = p.toString();
  return `/tickets${qs ? `?${qs}` : ""}`;
}

export const listTickets = (f: TicketFilters = {}) =>
  api<Envelope<Page<Ticket>>>(ticketsUrl(f));

export const getTicket = (id: string) =>
  api<Envelope<TicketDetail>>(`/tickets/${id}`);

export const createTicket = (payload: Record<string, unknown>) =>
  api<Envelope<Ticket>>("/tickets", { method: "POST", body: JSON.stringify(payload) });

export const updateTicket = (id: string, payload: Record<string, unknown>) =>
  api<Envelope<Ticket>>(`/tickets/${id}`, { method: "PATCH", body: JSON.stringify(payload) });

export const transitionTicket = (id: string, status: string, reason?: string) =>
  api<Envelope<Ticket>>(`/tickets/${id}/status`, {
    method: "POST",
    body: JSON.stringify({ status, reason }),
  });

export const scoreTicket = (id: string) =>
  api<Envelope<{ lead: number; intent: number; risk: number; confidence: number }>>(
    `/tickets/${id}/score`,
    { method: "POST" },
  );
