# LeadSynt — Privacy & Data Protection

## Consent

- Every `contacts` row has `consent_marketing` (bool) + `consent_source`
  (where consent was observed) — seeded defaults are **no consent** until
  proven by a connector payload or manual confirmation.
- Outreach creation requires the contact to have consent OR the ticket to be
  in a legitimate B2B response context; the check is enforced in
  `OutreachService` (server-side), and denials are audited.

## Suppression / DO-NOT-CONTACT

- `contacts.is_suppressed` (per contact) and the global `suppression_list`
  (email + domain granularity) are checked on **every** outreach attempt:
  suppressed → `403 { "code": "suppressed_contact" }`, audited, no message sent.
- A suppression hit is sticky: it can only be cleared by an admin with audit.
- Test coverage: `test_suppression.py`.

## Data minimization & provenance

- We store what the pipeline needs: contact/company facts, requirement
  content, verification evidence. Raw connector payloads live in
  `source_items` with a content hash and a retention flag.
- Every derived fact carries provenance (source URL, discovered/verified
  when+by, confidence). Unverified values are explicitly `UNKNOWN`/
  `UNVERIFIED` — the system never stores a guess as fact.

## Retention

- `settings` key `retention_days` (default 365, admin-editable) drives a
  scheduled retention review (Celery task; the sweep flags expired
  records rather than deleting silently).
- Terminal tickets (WON/LOST/ARCHIVED) are candidates for archive after the
  retention window; deletion is a deliberate admin action with audit.

## Outreach ethics guardrails

1. No automated follow-up after a reply — handover to a human (hard rule).
2. No outreach to suppressed contacts (hard block).
3. No CAPTCHA/paywall/anti-bot bypass — connectors use official APIs,
   permitted pages, feeds, licensed data only (connector metadata records
   compliance notes per connector).
4. Each `outreach_message` stores channel, content, and the rule-set version
   that authorized it — full reconstruction of "why did we send this" is
   possible from the data.

## Auditability

Privacy-relevant actions (suppression, consent change, handover,
deactivation) all emit `audit_logs` rows. The `/admin/audit` endpoint
supports filtering by action/entity/user for compliance reviews.
