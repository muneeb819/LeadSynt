# LeadSynt — Frontend Development Guide

## Stack

Next.js 14 (App Router, TypeScript strict) · React 18 · Tailwind (dark-first,
zinc-950 + indigo accent) · no external UI kit.

Build mode: `output: "standalone"` — `npm run build` additionally emits a
self-contained `frontend/.next/standalone/server.js` (own `node_modules`).
The root Docker image runs **that** server next to the API in one container
(one port: 3000). `next dev` / `next start` work as before for local use.

## Layout

```
frontend/
  app/
    layout.tsx           # theme provider + auth provider
    page.tsx             # → /dashboard
    login/  dashboard/  tickets/  tickets/[id]/
    leads/ contacts/ companies/ agents/ qa/ analytics/
    sources/ outreach/ conversations/ deals/ marketplace/
    settings/ admin/
  components/
    ui/                  # Button, Card, Badge, Input, Select, Table,
                         # StatusPill, ScoreBar, EmptyState
    layout/              # AppShell (nav + user menu), PageHeader
    tickets/             # NewTicketDialog
    ModuleRoadmap.tsx    # shared "next phase" placeholder for roadmap modules
  lib/api-client.ts      # the ONLY fetch path to the API
  services/              # typed wrappers per domain (auth, tickets, …)
  state/auth-context.tsx # session, login/logout, token storage
  hooks/                 # useApi (SWR-lite), useTheme
  types/api.ts           # shared API types (Envelope, Ticket, …)
  utils/                 # cn, formatting
```

## Rules

1. **Same-origin only.** Components call `/api/v1/...`; `next.config.mjs`
   rewrites to the backend. Never put a backend URL or secret in client code.
2. **One API client.** `lib/api-client.ts` handles: Bearer header, JSON,
   one-shot 401 refresh (never on `/auth/*`), hard-401 → clear tokens →
   /login, error normalization to the backend's error contract.
3. **Server is authoritative.** `ROLE_PERMISSIONS` in
   `state/auth-context.tsx` mirrors the backend RBAC matrix for hiding UI —
   the API still enforces everything (403s are expected and handled).
4. **Types from `types/api.ts`** match the backend Pydantic schemas; when a
   schema changes, update both (the TS compiler + E2E check catch drift).
5. **No fake data in the UI.** Pages either show real API data or explicit
   "not yet implemented / next phase" (ModuleRoadmap). Empty states say why.
6. Theme: dark by default, class-based toggle; system fonts only.

## Adding a page

1. `app/<name>/page.tsx` + nav entry in `components/layout/AppShell.tsx`.
2. `services/<name>.ts` typed wrapper.
3. Use `useApi<T>` for data; `useAuth()` for permissions.
4. List pages: `Card` + `Table`, filters as local state, cursor/page
   pagination from the envelope.
5. Verify with the production build: `npm run build` (type-checks) and the
   E2E script.
